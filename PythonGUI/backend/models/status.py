from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from backend.models.frames import SpectrumFrame


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionState(str, Enum):
    disconnected = "disconnected"
    connecting = "connecting"
    connected = "connected"
    error = "error"


class DeviceStatus(BaseModel):
    connection_state: ConnectionState = ConnectionState.disconnected
    transport: str = "serial"
    port: str | None = None
    baudrate: int | None = None
    last_seen: datetime | None = None
    last_message: str | None = None
    last_error: str | None = None
    frame_counter: int = 0
    sample_count: int = 0
    effective_start_index: int = 32
    effective_sample_count: int = 3648
    missed_frames: int = 0
    last_frame_flags: int = 0
    sample_preview: list[int] = Field(default_factory=list)
    firmware_messages: list[str] = Field(default_factory=list)


class SessionStatus(BaseModel):
    session_id: str
    started_at: datetime = Field(default_factory=utc_now)
    frames_buffered: int = 0
    dropped_frames: int = 0
    last_export_path: str | None = None


class CommandResult(BaseModel):
    ok: bool
    message: str


class AppSnapshot(BaseModel):
    device: DeviceStatus
    session: SessionStatus
    spectrum: SpectrumFrame | None = None
    logs: list[str] = Field(default_factory=list)
