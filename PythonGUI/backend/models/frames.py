from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Purpose: return the current UTC time. Rationale: timestamp helpers should stay consistent across models."""
    return datetime.now(timezone.utc)


class BannerPacket(BaseModel):
    """Purpose: store a firmware banner line. Rationale: startup messages are useful but different from frame data."""
    kind: Literal["banner"] = "banner"
    text: str
    timestamp: datetime = Field(default_factory=utc_now)


class TextLinePacket(BaseModel):
    """Purpose: store a generic text line from the device. Rationale: not every incoming line is a structured banner or frame."""
    kind: Literal["text"] = "text"
    text: str
    timestamp: datetime = Field(default_factory=utc_now)


class FramePacket(BaseModel):
    """Purpose: represent one parsed incoming device frame. Rationale: packet parsing should produce a clean structured object."""
    kind: Literal["frame"] = "frame"
    frame_counter: int
    sample_count: int
    effective_start: int
    effective_count: int
    flags: int
    adc_counts: list[int]
    timestamp: datetime = Field(default_factory=utc_now)


DevicePacket: TypeAlias = BannerPacket | TextLinePacket | FramePacket


class SpectrumFrame(BaseModel):
    """Purpose: represent a frame inside the app. Rationale: the UI and exporters need a stable higher-level frame model."""
    frame_id: int
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = "usb_binary_frame"
    expected_sample_count: int = 3694
    effective_start_index: int = 32
    effective_sample_count: int = 3648
    frame_flags: int = 0
    sample_indices: list[int] = Field(default_factory=list)
    adc_counts: list[int] = Field(default_factory=list)
    live_display_counts: list[float] = Field(default_factory=list)
    spectrogram_row: list[float] = Field(default_factory=list)
    dark_reference_count: float | None = None
    volts: list[float] = Field(default_factory=list)
    wavelengths_nm: list[float] = Field(default_factory=list)
    processed_intensity: list[float] = Field(default_factory=list)
    notes: str | None = None


class SpectrogramHistoryFrame(BaseModel):
    """Purpose: represent one compact spectrogram-history row. Rationale: the rolling heatmap needs longer time coverage than the full export buffer can hold affordably."""
    frame_id: int
    timestamp: datetime = Field(default_factory=utc_now)
    spectrogram_row: list[float] = Field(default_factory=list)
