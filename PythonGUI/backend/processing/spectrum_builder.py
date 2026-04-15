from __future__ import annotations

from typing import Sequence

import numpy as np

from backend.models.config import DeviceConfig
from backend.models.frames import FramePacket, SpectrumFrame
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.adc_converter import counts_to_volts
from backend.processing.dark_subtraction import apply_dark_subtraction
from backend.processing.intensity_correction import apply_intensity_correction
from backend.processing.wavelength_map import indices_to_wavelengths


class SpectrumBuilder:
    def __init__(
        self,
        calibration_manager: CalibrationManager,
        device_config: DeviceConfig,
    ) -> None:
        self._calibration_manager = calibration_manager
        self._device_config = device_config
        self._cached_wavelengths: dict[tuple[int, tuple[float, ...]], np.ndarray] = {}

    def update_device_config(self, device_config: DeviceConfig) -> None:
        self._device_config = device_config

    def build_from_frame_packet(self, packet: FramePacket) -> SpectrumFrame:
        return SpectrumFrame(
            frame_id=packet.frame_counter,
            timestamp=packet.timestamp,
            source="usb_binary_frame",
            expected_sample_count=packet.sample_count,
            effective_start_index=packet.effective_start,
            effective_sample_count=packet.effective_count,
            frame_flags=packet.flags,
            adc_counts=packet.adc_counts,
            notes=(
                "Captured from TIM4-synchronized USB CDC binary frames. Frame start is "
                "the CCD ICG low-to-high edge and frame end is the CCD ICG high-to-low edge."
            ),
        )

    def build_export_columns(
        self,
        *,
        adc_counts: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sample_count = len(adc_counts)
        raw_counts = np.asarray(adc_counts, dtype=float)
        corrected_counts = raw_counts
        calibration_config = self._calibration_manager.config

        if calibration_config.apply_dark_subtraction:
            corrected_counts = apply_dark_subtraction(
                corrected_counts,
                calibration_config.dark_offset_counts,
            )

        volts = counts_to_volts(
            corrected_counts,
            reference_volts=self._device_config.adc_reference_volts,
            resolution_bits=self._device_config.adc_resolution_bits,
        )

        intensity = volts
        if calibration_config.apply_intensity_correction:
            intensity = apply_intensity_correction(
                intensity,
                calibration_config.intensity_correction,
            )

        coefficient_key = tuple(calibration_config.wavelength_coefficients)
        cache_key = (sample_count, coefficient_key)
        wavelengths = self._cached_wavelengths.get(cache_key)
        if wavelengths is None:
            wavelengths = indices_to_wavelengths(
                range(sample_count),
                calibration_config.wavelength_coefficients,
            )
            self._cached_wavelengths = {cache_key: wavelengths}

        return wavelengths, volts, intensity
