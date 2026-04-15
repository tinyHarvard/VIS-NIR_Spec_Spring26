from __future__ import annotations

from typing import Sequence

import numpy as np

from backend.models.config import CalibrationConfig, DeviceConfig
from backend.processing.adc_converter import counts_to_volts
from backend.processing.dark_subtraction import apply_dark_subtraction
from backend.processing.intensity_correction import apply_intensity_correction
from backend.processing.wavelength_map import indices_to_wavelengths


class CalibrationManager:
    def __init__(self, config: CalibrationConfig) -> None:
        self._config = config

    @property
    def config(self) -> CalibrationConfig:
        return self._config

    def update_config(self, config: CalibrationConfig) -> None:
        self._config = config

    def apply(
        self,
        sample_indices: Sequence[int],
        adc_counts: Sequence[int],
        device_config: DeviceConfig,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        raw_counts = np.asarray(adc_counts, dtype=float)
        corrected_counts = raw_counts

        if self._config.apply_dark_subtraction:
            corrected_counts = apply_dark_subtraction(
                corrected_counts,
                self._config.dark_offset_counts,
                sample_indices=sample_indices,
            )

        volts = counts_to_volts(
            corrected_counts,
            reference_volts=device_config.adc_reference_volts,
            resolution_bits=device_config.adc_resolution_bits,
        )

        intensity = volts
        if self._config.apply_intensity_correction:
            intensity = apply_intensity_correction(
                intensity,
                self._config.intensity_correction,
                sample_indices=sample_indices,
            )

        wavelengths = indices_to_wavelengths(
            sample_indices,
            self._config.wavelength_coefficients,
        )
        return wavelengths, volts, intensity
