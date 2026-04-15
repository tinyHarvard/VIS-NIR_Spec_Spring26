from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Sequence

from backend.models.frames import SpectrumFrame

if TYPE_CHECKING:
    from backend.processing.spectrum_builder import SpectrumBuilder


def export_spectra_csv(
    path: Path,
    frames: Sequence[SpectrumFrame],
    *,
    spectrum_builder: "SpectrumBuilder | None" = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frame_id",
                "timestamp",
                "source",
                "expected_sample_count",
                "effective_start_index",
                "effective_sample_count",
                "frame_flags",
                "sample_index",
                "wavelength_nm",
                "adc_count",
                "volts",
                "processed_intensity",
            ]
        )

        for frame in frames:
            row_count = max(len(frame.adc_counts), len(frame.sample_indices))
            wavelengths = frame.wavelengths_nm
            volts = frame.volts
            intensity = frame.processed_intensity

            if spectrum_builder is not None and (
                len(wavelengths) < row_count
                or len(volts) < row_count
                or len(intensity) < row_count
            ):
                export_wavelengths, export_volts, export_intensity = spectrum_builder.build_export_columns(
                    adc_counts=frame.adc_counts,
                )
                wavelengths = export_wavelengths.tolist()
                volts = export_volts.tolist()
                intensity = export_intensity.tolist()

            for index in range(row_count):
                writer.writerow(
                    [
                        frame.frame_id,
                        frame.timestamp.isoformat(),
                        frame.source,
                        frame.expected_sample_count,
                        frame.effective_start_index,
                        frame.effective_sample_count,
                        frame.frame_flags,
                        frame.sample_indices[index] if index < len(frame.sample_indices) else index,
                        wavelengths[index] if index < len(wavelengths) else "",
                        frame.adc_counts[index] if index < len(frame.adc_counts) else "",
                        volts[index] if index < len(volts) else "",
                        intensity[index] if index < len(intensity) else "",
                    ]
                )

    return path
