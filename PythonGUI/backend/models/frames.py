from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BannerPacket(BaseModel):
    kind: Literal["banner"] = "banner"
    text: str
    timestamp: datetime = Field(default_factory=utc_now)


class TextLinePacket(BaseModel):
    kind: Literal["text"] = "text"
    text: str
    timestamp: datetime = Field(default_factory=utc_now)


class FramePacket(BaseModel):
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
    frame_id: int
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = "usb_binary_frame"
    expected_sample_count: int = 3694
    effective_start_index: int = 32
    effective_sample_count: int = 3648
    frame_flags: int = 0
    sample_indices: list[int] = Field(default_factory=list)
    adc_counts: list[int] = Field(default_factory=list)
    volts: list[float] = Field(default_factory=list)
    wavelengths_nm: list[float] = Field(default_factory=list)
    processed_intensity: list[float] = Field(default_factory=list)
    notes: str | None = None
