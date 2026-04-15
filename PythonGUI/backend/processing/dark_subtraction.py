from __future__ import annotations

from typing import Sequence

import numpy as np


def apply_dark_subtraction(
    values: Sequence[float],
    dark_offsets: Sequence[float],
    sample_indices: Sequence[int] | None = None,
) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    if not dark_offsets:
        return data

    dark = np.asarray(dark_offsets, dtype=float)
    if sample_indices is None:
        limit = min(len(data), len(dark))
        corrected = data.copy()
        corrected[:limit] -= dark[:limit]
        return corrected

    lookup = np.array(
        [dark[index] if 0 <= index < len(dark) else 0.0 for index in sample_indices],
        dtype=float,
    )
    return data - lookup
