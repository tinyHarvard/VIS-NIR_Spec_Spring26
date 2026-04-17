from __future__ import annotations

from typing import Sequence

import numpy as np


def apply_intensity_correction(
    values: Sequence[float],
    correction_factors: Sequence[float],
    sample_indices: Sequence[int] | None = None,
) -> np.ndarray:
    """Purpose: apply multiplicative correction factors. Rationale: gain correction should stay separate from raw signal capture."""
    data = np.asarray(values, dtype=float)
    if not correction_factors:
        return data

    factors = np.asarray(correction_factors, dtype=float)
    if sample_indices is None:
        limit = min(len(data), len(factors))
        corrected = data.copy()
        corrected[:limit] *= factors[:limit]
        return corrected

    lookup = np.array(
        [factors[index] if 0 <= index < len(factors) else 1.0 for index in sample_indices],
        dtype=float,
    )
    return data * lookup
