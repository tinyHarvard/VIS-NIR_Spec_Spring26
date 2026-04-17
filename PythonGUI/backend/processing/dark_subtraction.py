from __future__ import annotations

from typing import Sequence

import numpy as np


def estimate_dark_level(
    values: Sequence[float],
    *,
    start_index: int,
    end_index: int,
) -> float:
    """Purpose: estimate one dark baseline from a shielded-pixel region. Rationale: some sensors provide covered pixels that can be averaged each frame."""
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        return 0.0

    start = max(0, start_index)
    stop = min(len(data), end_index + 1)
    if stop <= start:
        return 0.0

    return float(np.mean(data[start:stop]))


def subtract_dark_level(
    values: Sequence[float],
    dark_level: float,
    *,
    clip_min: float | None = None,
) -> np.ndarray:
    """Purpose: subtract one scalar dark baseline from all samples. Rationale: frame-wide bias removal is cheaper than storing a full dark vector."""
    corrected = np.asarray(values, dtype=float) - float(dark_level)
    if clip_min is not None:
        corrected = np.maximum(corrected, clip_min)
    return corrected


def apply_dark_subtraction(
    values: Sequence[float],
    dark_offsets: Sequence[float],
    sample_indices: Sequence[int] | None = None,
) -> np.ndarray:
    """Purpose: subtract dark offsets from signal values. Rationale: sensor bias removal should be reusable and data-driven."""
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
