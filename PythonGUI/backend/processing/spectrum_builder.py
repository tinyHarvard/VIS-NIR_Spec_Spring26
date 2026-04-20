from __future__ import annotations

from contextlib import nullcontext
from typing import Sequence

import numpy as np

from backend.core.performance_monitor import PerformanceMonitor
from backend.models.config import DeviceConfig
from backend.models.frames import FramePacket, SpectrumFrame
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.adc_converter import counts_to_volts
from backend.processing.dark_subtraction import apply_dark_subtraction, estimate_dark_level
from backend.processing.intensity_correction import apply_intensity_correction
from backend.processing.wavelength_map import indices_to_wavelengths

FRAME_DARK_START_INDEX = 16
FRAME_DARK_END_INDEX = 28
LIVE_DISPLAY_CLIP_MIN = 0.0
NORMALIZED_SIGNAL_MAX = 1.0
MIN_NORMALIZATION_DENOMINATOR = 1e-9
SPECTROGRAM_ROW_TARGET_WIDTH = 256
SPECTROGRAM_ROW_PEAK_BLEND = 0.15


class SpectrumBuilder:
    """Purpose: build app-level spectrum frames and export columns. Rationale: frame conversion should stay separate from transport parsing."""
    def __init__(
        self,
        calibration_manager: CalibrationManager,
        device_config: DeviceConfig,
        *,
        performance_monitor: PerformanceMonitor | None = None,
    ) -> None:
        """Purpose: store processing dependencies and caches. Rationale: repeated export calculations should reuse device settings and wavelength maps."""
        self._calibration_manager = calibration_manager
        self._device_config = device_config
        self._cached_wavelengths: dict[tuple[int, tuple[float, ...]], np.ndarray] = {}
        self._performance_monitor = performance_monitor

    def update_device_config(self, device_config: DeviceConfig) -> None:
        """Purpose: store updated device settings. Rationale: export calculations should follow the latest ADC and geometry configuration."""
        self._device_config = device_config

    def build_from_frame(self, frame: FramePacket) -> SpectrumFrame:
        """Purpose: wrap one parsed device frame as a spectrum frame. Rationale: the rest of the app should work with one stable frame type."""
        monitor = self._performance_monitor
        with (
            monitor.measure("backend.build_from_frame")
            if monitor is not None
            else nullcontext()
        ):
            (
                processed_counts,
                display_counts,
                _wavelengths,
                _volts,
                dark_reference,
                saturation_reference_counts,
            ) = self._build_processed_columns(frame.adc_counts)
            spectrogram_values = self._normalize_spectrogram_signal(
                processed_counts,
                saturation_reference_counts=saturation_reference_counts,
            )
            spectrogram_row = self._build_spectrogram_row(
                spectrogram_values,
                expected_sample_count=frame.sample_count,
                effective_start_index=frame.effective_start,
                effective_sample_count=frame.effective_count,
            )
            return SpectrumFrame(
                frame_id=frame.frame_counter,
                timestamp=frame.timestamp,
                source="usb_binary_frame",
                expected_sample_count=frame.sample_count,
                effective_start_index=frame.effective_start,
                effective_sample_count=frame.effective_count,
                frame_flags=frame.flags,
                adc_counts=frame.adc_counts,
                live_display_counts=display_counts.tolist(),
                spectrogram_row=spectrogram_row,
                dark_reference_count=dark_reference,
                notes=(
                    "Captured from TIM4-synchronized USB CDC binary frames. Frame start is "
                    "the CCD ICG low-to-high edge and frame end is the CCD ICG high-to-low edge."
                ),
            )

    def rebuild_live_frame(self, frame: SpectrumFrame) -> SpectrumFrame:
        """Purpose: rebuild one stored frame using the current calibration settings. Rationale: UI calibration toggles should update the latest display immediately."""
        monitor = self._performance_monitor
        with (
            monitor.measure("backend.rebuild_live_frame")
            if monitor is not None
            else nullcontext()
        ):
            (
                processed_counts,
                display_counts,
                _wavelengths,
                _volts,
                dark_reference,
                saturation_reference_counts,
            ) = self._build_processed_columns(frame.adc_counts)
            spectrogram_values = self._normalize_spectrogram_signal(
                processed_counts,
                saturation_reference_counts=saturation_reference_counts,
            )
            updated = frame.model_copy(deep=True)
            updated.live_display_counts = display_counts.tolist()
            updated.spectrogram_row = self._build_spectrogram_row(
                spectrogram_values,
                expected_sample_count=frame.expected_sample_count,
                effective_start_index=frame.effective_start_index,
                effective_sample_count=frame.effective_sample_count,
            )
            updated.dark_reference_count = dark_reference
            return updated

    def build_export_columns(
        self,
        *,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Purpose: compute export-time wavelength and intensity columns. Rationale: heavy derived data should be delayed until it is actually needed."""
        (
            corrected_counts,
            normalized_counts,
            wavelengths,
            volts,
            frame_dark_level,
            _saturation_reference_counts,
        ) = self._build_processed_columns(adc_counts)
        return corrected_counts, wavelengths, volts, normalized_counts, frame_dark_level

    def _build_processed_counts(
        self,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """Purpose: build corrected count series and a final normalized display signal. Rationale: document-style calibration needs additive terms removed before multiplicative corrections and only then normalized."""
        (
            corrected_counts,
            normalized_counts,
            _wavelengths,
            _volts,
            frame_dark_level,
            _saturation_reference_counts,
        ) = self._build_processed_columns(adc_counts)
        return corrected_counts, normalized_counts, frame_dark_level

    def _build_live_display_counts(
        self,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, float]:
        """Purpose: build the live plot series from raw ADC counts. Rationale: the UI should display normalized processed data without mutating the captured raw frame."""
        _processed_counts, normalized_counts, frame_dark_level = self._build_processed_counts(adc_counts)
        return normalized_counts, frame_dark_level

    def _build_processed_columns(
        self,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
        """Purpose: run the calibration pipeline through corrected counts, wavelength assignment, and final normalization. Rationale: both the live plot and CSV export should use the same ordered processing steps."""
        monitor = self._performance_monitor
        with (
            monitor.measure("backend.build_processed_columns")
            if monitor is not None
            else nullcontext()
        ):
            raw_counts = np.asarray(adc_counts, dtype=float)
            full_scale_count = float((1 << self._device_config.adc_resolution_bits) - 1)
            calibration_config = self._calibration_manager.config
            bias_corrected_raw = raw_counts.copy()
            if calibration_config.bias_counts:
                bias_corrected_raw = apply_dark_subtraction(
                    bias_corrected_raw,
                    calibration_config.bias_counts,
                )
            saturated_bias_corrected_raw = np.zeros_like(raw_counts, dtype=float)
            if calibration_config.bias_counts:
                saturated_bias_corrected_raw = apply_dark_subtraction(
                    saturated_bias_corrected_raw,
                    calibration_config.bias_counts,
                )

            frame_dark_level = 0.0
            if calibration_config.apply_dark_subtraction:
                # The document defines beta_f from the dark pixels after removing the
                # stored master bias B_p, so the frame-wise offset here is measured
                # on the bias-corrected raw frame. Because this CCD is inverted in
                # our readout, the light-tracking signal is then the distance from
                # that dark baseline down to the current sample.
                frame_dark_level = estimate_dark_level(
                    bias_corrected_raw,
                    start_index=FRAME_DARK_START_INDEX,
                    end_index=FRAME_DARK_END_INDEX,
                )
            light_counts = self._light_counts_from_bias_corrected_raw(
                bias_corrected_raw,
                frame_dark_level=frame_dark_level,
                full_scale_count=full_scale_count,
                apply_dark_subtraction_enabled=calibration_config.apply_dark_subtraction,
                dark_offset_counts=calibration_config.dark_offset_counts,
            )
            saturation_light_counts = self._light_counts_from_bias_corrected_raw(
                saturated_bias_corrected_raw,
                frame_dark_level=frame_dark_level,
                full_scale_count=full_scale_count,
                apply_dark_subtraction_enabled=calibration_config.apply_dark_subtraction,
                dark_offset_counts=calibration_config.dark_offset_counts,
            )

            wavelengths = self._wavelengths_for_sample_count(len(raw_counts))
            corrected_counts, saturation_reference_counts = self._apply_multiplicative_corrections(
                light_counts,
                saturation_light_counts,
                wavelengths=wavelengths,
            )

            corrected_counts = np.maximum(corrected_counts, LIVE_DISPLAY_CLIP_MIN)
            volts = counts_to_volts(
                light_counts,
                reference_volts=self._device_config.adc_reference_volts,
                resolution_bits=self._device_config.adc_resolution_bits,
            )
            normalized_counts = self._normalize_processed_signal(
                corrected_counts,
                saturation_reference_counts=saturation_reference_counts,
            )
            return corrected_counts, normalized_counts, wavelengths, volts, frame_dark_level, saturation_reference_counts

    def _build_spectrogram_row(
        self,
        normalized_spectrogram_values: Sequence[float] | np.ndarray,
        *,
        expected_sample_count: int,
        effective_start_index: int,
        effective_sample_count: int,
    ) -> list[float]:
        """Purpose: prepare one compact spectrogram row alongside live-frame processing. Rationale: the spectrogram should use a stable value scale even when the line plot is using per-frame auto-ranging."""
        monitor = self._performance_monitor
        with (
            monitor.measure("backend.build_spectrogram_row")
            if monitor is not None
            else nullcontext()
        ):
            values = np.asarray(normalized_spectrogram_values, dtype=float)
            total_samples = len(values)
            if total_samples <= 0:
                return []

            if total_samples >= expected_sample_count:
                start = max(int(effective_start_index), 0)
                end = min(start + max(int(effective_sample_count), 0), total_samples)
                active_values = values[start:end]
            else:
                active_values = values

            if active_values.size <= 0:
                return []
            return self._compress_spectrogram_row(active_values, target_width=SPECTROGRAM_ROW_TARGET_WIDTH)

    @staticmethod
    def _compress_spectrogram_row(values: np.ndarray, *, target_width: int) -> list[float]:
        """Purpose: reduce one normalized frame row to a fixed spectrogram width. Rationale: the heatmap should grade by overall segment level instead of letting one hot sample dominate the whole bucket."""
        if values.size <= 0:
            return []

        safe_target_width = max(int(target_width), 1)
        clipped_values = np.clip(np.asarray(values, dtype=float), LIVE_DISPLAY_CLIP_MIN, NORMALIZED_SIGNAL_MAX)
        source_width = int(clipped_values.size)

        if source_width <= safe_target_width:
            padded = clipped_values.tolist()
            if len(padded) < safe_target_width:
                padded.extend([padded[-1]] * (safe_target_width - len(padded)))
            return padded

        boundaries = np.linspace(0, source_width, safe_target_width + 1, dtype=int)
        compressed: list[float] = []
        for column_index in range(safe_target_width):
            start = int(boundaries[column_index])
            end = max(int(boundaries[column_index + 1]), start + 1)
            segment = clipped_values[start:end]
            segment_peak = float(np.max(segment))
            segment_rms = float(np.sqrt(np.mean(segment * segment)))
            blended_value = (
                (segment_rms * (1.0 - SPECTROGRAM_ROW_PEAK_BLEND))
                + (segment_peak * SPECTROGRAM_ROW_PEAK_BLEND)
            )
            compressed.append(min(max(blended_value, LIVE_DISPLAY_CLIP_MIN), NORMALIZED_SIGNAL_MAX))
        return compressed

    def _light_counts_from_bias_corrected_raw(
        self,
        bias_corrected_raw: Sequence[float],
        *,
        frame_dark_level: float,
        full_scale_count: float,
        apply_dark_subtraction_enabled: bool,
        dark_offset_counts: Sequence[float],
    ) -> np.ndarray:
        """Purpose: convert bias-corrected raw CCD codes into light-tracking counts. Rationale: the same additive logic should be reused for the live frame and the absolute-saturation reference frame."""
        raw = np.asarray(bias_corrected_raw, dtype=float)
        if apply_dark_subtraction_enabled:
            dark_corrected_raw = apply_dark_subtraction(
                raw,
                dark_offset_counts,
            )
            return np.maximum(
                frame_dark_level - dark_corrected_raw,
                LIVE_DISPLAY_CLIP_MIN,
            )
        return np.maximum(
            full_scale_count - raw,
            LIVE_DISPLAY_CLIP_MIN,
        )

    def _apply_multiplicative_corrections(
        self,
        light_counts: Sequence[float],
        saturation_light_counts: Sequence[float],
        *,
        wavelengths: Sequence[float],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Purpose: apply flat-field and QE-style multiplicative corrections to both the live signal and its saturation reference. Rationale: absolute saturation mode only works if the denominator sees the same multiplicative processing as the numerator."""
        calibration_config = self._calibration_manager.config
        corrected_counts = np.asarray(light_counts, dtype=float)
        saturation_reference_counts = np.asarray(saturation_light_counts, dtype=float)

        if calibration_config.apply_intensity_correction:
            corrected_counts = apply_intensity_correction(
                corrected_counts,
                calibration_config.intensity_correction,
            )
            saturation_reference_counts = apply_intensity_correction(
                saturation_reference_counts,
                calibration_config.intensity_correction,
            )

        if calibration_config.apply_quantum_efficiency_correction:
            qe_curve = self._calibration_manager.build_quantum_efficiency_curve(wavelengths)
            corrected_counts = corrected_counts / qe_curve
            saturation_reference_counts = saturation_reference_counts / qe_curve

        corrected_counts = np.maximum(corrected_counts, LIVE_DISPLAY_CLIP_MIN)
        saturation_reference_counts = np.maximum(saturation_reference_counts, MIN_NORMALIZATION_DENOMINATOR)
        return corrected_counts, saturation_reference_counts

    def _wavelengths_for_sample_count(self, sample_count: int) -> np.ndarray:
        """Purpose: reuse wavelength arrays for a given sample count and coefficient set. Rationale: live export calculations should not keep rebuilding the same polynomial map."""
        calibration_config = self._calibration_manager.config
        coefficient_key = tuple(calibration_config.wavelength_coefficients)
        cache_key = (sample_count, coefficient_key)
        wavelengths = self._cached_wavelengths.get(cache_key)
        if wavelengths is None:
            wavelengths = indices_to_wavelengths(
                range(sample_count),
                calibration_config.wavelength_coefficients,
            )
            self._cached_wavelengths = {cache_key: wavelengths}
        return wavelengths

    def _normalize_processed_signal(
        self,
        processed_counts: Sequence[float],
        *,
        saturation_reference_counts: Sequence[float],
    ) -> np.ndarray:
        """Purpose: normalize the fully corrected signal into the 0-to-1 display range. Rationale: the UI needs both auto-ranging and absolute saturation-referenced views of the same processed signal."""
        processed = np.asarray(processed_counts, dtype=float)
        normalization_mode = self._calibration_manager.config.display_normalization_mode
        if normalization_mode == "absolute_saturation":
            denominator = np.maximum(
                np.asarray(saturation_reference_counts, dtype=float),
                MIN_NORMALIZATION_DENOMINATOR,
            )
        else:
            denominator = max(float(np.max(processed, initial=0.0)), MIN_NORMALIZATION_DENOMINATOR)
        normalized = processed / denominator
        return np.clip(normalized, LIVE_DISPLAY_CLIP_MIN, NORMALIZED_SIGNAL_MAX)

    def _normalize_spectrogram_signal(
        self,
        processed_counts: Sequence[float],
        *,
        saturation_reference_counts: Sequence[float],
    ) -> np.ndarray:
        """Purpose: build a stable spectrogram value scale from processed counts. Rationale: rolling heatmap colors should stay comparable from frame to frame even when the line plot uses auto-peak normalization."""
        processed = np.asarray(processed_counts, dtype=float)
        denominator = np.maximum(
            np.asarray(saturation_reference_counts, dtype=float),
            MIN_NORMALIZATION_DENOMINATOR,
        )
        normalized = processed / denominator
        return np.clip(normalized, LIVE_DISPLAY_CLIP_MIN, NORMALIZED_SIGNAL_MAX)
