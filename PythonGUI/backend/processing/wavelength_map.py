from __future__ import annotations

from typing import Sequence

import numpy as np


def indices_to_wavelengths(
    sample_indices: Sequence[int],
    coefficients: Sequence[float],
) -> np.ndarray:
    """Purpose: map sample indices to wavelengths. Rationale: wavelength calibration should come from coefficients rather than hard-coded tables."""
    indices = np.asarray(sample_indices, dtype=float)
    if not coefficients:
        return indices

    wavelengths = np.zeros_like(indices, dtype=float)
    for power, coefficient in enumerate(coefficients):
        wavelengths += float(coefficient) * np.power(indices, power)
    return wavelengths
