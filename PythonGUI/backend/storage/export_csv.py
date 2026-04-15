from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from backend.models.frames import SpectrumFrame


def export_spectra_csv(path: Path, frames: Sequence[SpectrumFrame]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frame_id",
                "timestamp",
                "source",
                "expected_sample_count",
                "sample_index",
                "wavelength_nm",
                "adc_count",
                "volts",
                "processed_intensity",
            ]
        )

        for frame in frames:
            row_count = len(frame.sample_indices)
            for index in range(row_count):
                writer.writerow(
                    [
                        frame.frame_id,
                        frame.timestamp.isoformat(),
                        frame.source,
                        frame.expected_sample_count,
                        frame.sample_indices[index],
                        frame.wavelengths_nm[index] if index < len(frame.wavelengths_nm) else "",
                        frame.adc_counts[index] if index < len(frame.adc_counts) else "",
                        frame.volts[index] if index < len(frame.volts) else "",
                        frame.processed_intensity[index]
                        if index < len(frame.processed_intensity)
                        else "",
                    ]
                )

    return path
