from __future__ import annotations

from typing import Sequence

import numpy as np

from backend.models.config import DeviceConfig
from backend.models.frames import FramePacket, SpectrumFrame
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.adc_converter import counts_to_volts
from backend.processing.dark_subtraction import apply_dark_subtraction, estimate_dark_level, subtract_dark_level
from backend.processing.intensity_correction import apply_intensity_correction
from backend.processing.wavelength_map import indices_to_wavelengths

FRAME_DARK_START_INDEX = 16
FRAME_DARK_END_INDEX = 28
LIVE_DISPLAY_CLIP_MIN = 0.0
NORMALIZED_SIGNAL_MAX = 1.0


class SpectrumBuilder:
    """Purpose: build app-level spectrum frames and export columns. Rationale: frame conversion should stay separate from transport parsing."""
    def __init__(
        self,
        calibration_manager: CalibrationManager,
        device_config: DeviceConfig,
    ) -> None:
        """Purpose: store processing dependencies and caches. Rationale: repeated export calculations should reuse device settings and wavelength maps."""
        self._calibration_manager = calibration_manager
        self._device_config = device_config
        self._cached_wavelengths: dict[tuple[int, tuple[float, ...]], np.ndarray] = {}

    def update_device_config(self, device_config: DeviceConfig) -> None:
        """Purpose: store updated device settings. Rationale: export calculations should follow the latest ADC and geometry configuration."""
        self._device_config = device_config

    def build_from_frame_packet(self, packet: FramePacket) -> SpectrumFrame:
        """Purpose: wrap a parsed frame packet as a spectrum frame. Rationale: the rest of the app should work with one stable frame type."""
        display_counts, dark_reference = self._build_live_display_counts(packet.adc_counts)
        return SpectrumFrame(
            frame_id=packet.frame_counter,
            timestamp=packet.timestamp,
            source="usb_binary_frame",
            expected_sample_count=packet.sample_count,
            effective_start_index=packet.effective_start,
            effective_sample_count=packet.effective_count,
            frame_flags=packet.flags,
            adc_counts=packet.adc_counts,
            live_display_counts=display_counts.tolist(),
            dark_reference_count=dark_reference,
            notes=(
                "Captured from TIM4-synchronized USB CDC binary frames. Frame start is "
                "the CCD ICG low-to-high edge and frame end is the CCD ICG high-to-low edge."
            ),
        )

    def rebuild_live_frame(self, frame: SpectrumFrame) -> SpectrumFrame:
        """Purpose: rebuild one stored frame using the current calibration settings. Rationale: UI calibration toggles should update the latest display immediately."""
        display_counts, dark_reference = self._build_live_display_counts(frame.adc_counts)
        updated = frame.model_copy(deep=True)
        updated.live_display_counts = display_counts.tolist()
        updated.dark_reference_count = dark_reference
        return updated

    def build_export_columns(
        self,
        *,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Purpose: compute export-time wavelength and intensity columns. Rationale: heavy derived data should be delayed until it is actually needed."""
        sample_count = len(adc_counts)
        corrected_counts, normalized_counts, frame_dark_level = self._build_processed_counts(adc_counts)
        calibration_config = self._calibration_manager.config

        volts = counts_to_volts(
            corrected_counts,
            reference_volts=self._device_config.adc_reference_volts,
            resolution_bits=self._device_config.adc_resolution_bits,
        )

        intensity = normalized_counts
        if calibration_config.apply_intensity_correction:
            intensity = apply_intensity_correction(
                intensity,
                calibration_config.intensity_correction,
            )
            intensity = np.clip(intensity, LIVE_DISPLAY_CLIP_MIN, NORMALIZED_SIGNAL_MAX)

        coefficient_key = tuple(calibration_config.wavelength_coefficients)
        cache_key = (sample_count, coefficient_key)
        wavelengths = self._cached_wavelengths.get(cache_key)
        if wavelengths is None:
            wavelengths = indices_to_wavelengths(
                range(sample_count),
                calibration_config.wavelength_coefficients,
            )
            self._cached_wavelengths = {cache_key: wavelengths}

        return normalized_counts, wavelengths, volts, intensity, frame_dark_level

    def _build_processed_counts(
        self,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """Purpose: build processed count series from raw ADC counts. Rationale: live display and export should share the same dark-subtracted normalization."""
        raw_counts = np.asarray(adc_counts, dtype=float)
        display_counts = raw_counts.copy()
        frame_dark_level = 0.0
        calibration_config = self._calibration_manager.config

        if calibration_config.apply_dark_subtraction:
            frame_dark_level = estimate_dark_level(
                display_counts,
                start_index=FRAME_DARK_START_INDEX,
                end_index=FRAME_DARK_END_INDEX,
            )
            display_counts = subtract_dark_level(
                display_counts,
                frame_dark_level,
                clip_min=LIVE_DISPLAY_CLIP_MIN,
            )
            display_counts = apply_dark_subtraction(
                display_counts,
                calibration_config.dark_offset_counts,
            )
            display_counts = np.maximum(display_counts, LIVE_DISPLAY_CLIP_MIN)

        normalized_counts = self._normalize_lighting_levels(
            raw_counts,
            dark_reference_count=frame_dark_level,
        )
        return display_counts, normalized_counts, frame_dark_level

    def _build_live_display_counts(
        self,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, float]:
        """Purpose: build the live plot series from raw ADC counts. Rationale: the UI should display normalized processed data without mutating the captured raw frame."""
        _processed_counts, normalized_counts, frame_dark_level = self._build_processed_counts(adc_counts)
        return normalized_counts, frame_dark_level

    def _normalize_lighting_levels(
        self,
        raw_counts: Sequence[float],
        *,
        dark_reference_count: float,
    ) -> np.ndarray:
        """Purpose: normalize the signal so higher values mean more light. Rationale: the live graph should rise with illumination, not darkness."""
        full_scale_count = float((1 << self._device_config.adc_resolution_bits) - 1)
        calibration_config = self._calibration_manager.config
        baseline_dark = (
            min(max(dark_reference_count, LIVE_DISPLAY_CLIP_MIN), full_scale_count)
            if calibration_config.apply_dark_subtraction
            else full_scale_count
        )
        usable_span = max(baseline_dark, 1.0)
        normalized = (baseline_dark - np.asarray(raw_counts, dtype=float)) / usable_span
        return np.clip(normalized, LIVE_DISPLAY_CLIP_MIN, NORMALIZED_SIGNAL_MAX)
