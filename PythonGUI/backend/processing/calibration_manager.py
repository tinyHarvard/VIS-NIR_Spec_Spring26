from __future__ import annotations

from typing import Sequence

import numpy as np

from backend.models.config import CalibrationConfig, DeviceConfig, PixelMappingPoint, SpectralResponsePoint
from backend.processing.adc_converter import counts_to_volts
from backend.processing.dark_subtraction import apply_dark_subtraction
from backend.processing.intensity_correction import apply_intensity_correction
from backend.processing.wavelength_map import indices_to_wavelengths

MIN_RESPONSE_VALUE = 1e-9


class CalibrationManager:
    """Purpose: own calibration settings and apply them. Rationale: processing rules should be centralized instead of scattered."""
    def __init__(self, config: CalibrationConfig) -> None:
        """Purpose: store the initial calibration config. Rationale: downstream code should read calibration from one managed object."""
        self._config = config

    @property
    def config(self) -> CalibrationConfig:
        """Purpose: expose the current calibration config. Rationale: other services sometimes need read-only access to the settings."""
        return self._config

    def update_config(self, config: CalibrationConfig) -> None:
        """Purpose: replace the calibration config. Rationale: UI edits should update processing behavior without recreating the app."""
        self._config = config

    def capture_bias_from_frames(
        self,
        frames: Sequence[Sequence[int]],
    ) -> list[float]:
        """Purpose: build a master bias vector from covered-sensor frames. Rationale: the document's B_p term should come from a user-driven blackout capture rather than guessed constants."""
        if not frames:
            return []

        stacked = np.asarray(frames, dtype=float)
        if stacked.ndim != 2 or stacked.shape[1] == 0:
            return []
        return np.mean(stacked, axis=0).tolist()

    def fit_wavelength_coefficients(
        self,
        points: Sequence[PixelMappingPoint],
        *,
        fit_order: int,
    ) -> list[float]:
        """Purpose: fit wavelength polynomial coefficients from reference lines. Rationale: the calibration manager should turn user-entered pixel mappings into the polynomial used everywhere else."""
        if not points:
            return list(self._config.wavelength_coefficients)

        fit_degree = max(0, min(int(fit_order), len(points) - 1))
        pixels = np.asarray([point.pixel_index for point in points], dtype=float)
        wavelengths = np.asarray([point.wavelength_nm for point in points], dtype=float)
        coefficients_desc = np.polyfit(pixels, wavelengths, deg=fit_degree)
        return coefficients_desc[::-1].tolist()

    def build_quantum_efficiency_curve(
        self,
        wavelengths_nm: Sequence[float],
    ) -> np.ndarray:
        """Purpose: build a normalized QE/response curve sampled at the current wavelengths. Rationale: the live and export pipelines should consume an interpolated response curve instead of raw user-entered points."""
        points = self._config.quantum_efficiency_points
        if not points:
            return np.ones(len(wavelengths_nm), dtype=float)

        sorted_points = sorted(points, key=lambda item: item.wavelength_nm)
        source_wavelengths = np.asarray([point.wavelength_nm for point in sorted_points], dtype=float)
        source_values = np.asarray([point.relative_value for point in sorted_points], dtype=float)
        if source_wavelengths.size == 0:
            return np.ones(len(wavelengths_nm), dtype=float)

        evaluation_wavelengths = np.asarray(wavelengths_nm, dtype=float)
        interpolated = np.interp(
            evaluation_wavelengths,
            source_wavelengths,
            source_values,
            left=float(source_values[0]),
            right=float(source_values[-1]),
        )

        reference_wavelength = self._config.quantum_efficiency_normalization_wavelength_nm
        if reference_wavelength is None:
            normalization_value = float(np.max(source_values))
        else:
            normalization_value = float(
                np.interp(
                    float(reference_wavelength),
                    source_wavelengths,
                    source_values,
                    left=float(source_values[0]),
                    right=float(source_values[-1]),
                )
            )
        normalization_value = max(normalization_value, MIN_RESPONSE_VALUE)
        normalized = interpolated / normalization_value
        return np.clip(normalized, MIN_RESPONSE_VALUE, None)

    def apply(
        self,
        sample_indices: Sequence[int],
        adc_counts: Sequence[int],
        device_config: DeviceConfig,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Purpose: run the full calibration pipeline. Rationale: callers should ask one method for corrected outputs instead of chaining helpers manually."""
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
        if self._config.apply_quantum_efficiency_correction:
            corrected_curve = self.build_quantum_efficiency_curve(wavelengths)
            intensity = intensity / corrected_curve
        return wavelengths, volts, intensity
