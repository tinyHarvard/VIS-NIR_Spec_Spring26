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
    """Purpose: export buffered frames to CSV. Rationale: captured spectra should be easy to inspect with common analysis tools."""
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
                "raw_adc_count",
                "processed_adc_count",
                "frame_dark_reference_count",
                "volts",
                "processed_intensity",
            ]
        )

        for frame in frames:
            row_count = max(len(frame.adc_counts), len(frame.sample_indices))
            processed_counts = frame.live_display_counts
            dark_reference_count = frame.dark_reference_count
            wavelengths = frame.wavelengths_nm
            volts = frame.volts
            intensity = frame.processed_intensity

            if spectrum_builder is not None and (
                len(processed_counts) < row_count
                or
                len(wavelengths) < row_count
                or len(volts) < row_count
                or len(intensity) < row_count
            ):
                (
                    export_processed_counts,
                    export_wavelengths,
                    export_volts,
                    export_intensity,
                    export_dark_reference_count,
                ) = spectrum_builder.build_export_columns(
                    adc_counts=frame.adc_counts,
                )
                processed_counts = export_processed_counts.tolist()
                wavelengths = export_wavelengths.tolist()
                volts = export_volts.tolist()
                intensity = export_intensity.tolist()
                dark_reference_count = export_dark_reference_count

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
                        processed_counts[index] if index < len(processed_counts) else "",
                        dark_reference_count if dark_reference_count is not None else "",
                        volts[index] if index < len(volts) else "",
                        intensity[index] if index < len(intensity) else "",
                    ]
                )

    return path
