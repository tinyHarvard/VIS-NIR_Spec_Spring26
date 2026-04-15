from __future__ import annotations

from typing import Sequence

import numpy as np


def counts_to_volts(
    counts: Sequence[float],
    reference_volts: float,
    resolution_bits: int,
) -> np.ndarray:
    max_code = float((1 << resolution_bits) - 1)
    return np.asarray(counts, dtype=float) * reference_volts / max_code
