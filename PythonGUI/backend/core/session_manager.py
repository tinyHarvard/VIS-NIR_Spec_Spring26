from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.models.frames import SpectrumFrame
from backend.models.status import SessionStatus
from backend.storage.export_csv import export_spectra_csv

if TYPE_CHECKING:
    from backend.processing.spectrum_builder import SpectrumBuilder


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    def __init__(
        self,
        export_dir: Path,
        *,
        max_frames: int = 2000,
        spectrum_builder: "SpectrumBuilder | None" = None,
    ) -> None:
        self._lock = Lock()
        self._export_dir = export_dir
        self._max_frames = max_frames
        self._frames: deque[SpectrumFrame] = deque(maxlen=max_frames)
        self._spectrum_builder = spectrum_builder
        self._session_id = self._new_session_id()
        self._started_at = utc_now()
        self._dropped_frames = 0
        self._last_export_path: str | None = None

    @staticmethod
    def _new_session_id() -> str:
        return uuid4().hex[:8]

    def set_max_frames(self, max_frames: int) -> None:
        with self._lock:
            current_frames = list(self._frames)[-max_frames:]
            if len(self._frames) > max_frames:
                self._dropped_frames += len(self._frames) - max_frames
            self._max_frames = max_frames
            self._frames = deque(current_frames, maxlen=max_frames)

    def append_frame(self, frame: SpectrumFrame) -> None:
        with self._lock:
            if len(self._frames) == self._frames.maxlen:
                self._dropped_frames += 1
            self._frames.append(frame)

    def set_spectrum_builder(self, spectrum_builder: "SpectrumBuilder") -> None:
        with self._lock:
            self._spectrum_builder = spectrum_builder

    def reset(self) -> None:
        with self._lock:
            self._frames.clear()
            self._session_id = self._new_session_id()
            self._started_at = utc_now()
            self._dropped_frames = 0
            self._last_export_path = None

    def export_csv(self) -> Path:
        with self._lock:
            timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
            path = self._export_dir / f"spectrometer_session_{timestamp}.csv"
            frames = list(self._frames)
            spectrum_builder = self._spectrum_builder
        export_spectra_csv(path, frames, spectrum_builder=spectrum_builder)
        with self._lock:
            self._last_export_path = str(path)
            return path

    def frames(self) -> list[SpectrumFrame]:
        with self._lock:
            return list(self._frames)

    def status(self) -> SessionStatus:
        with self._lock:
            return SessionStatus(
                session_id=self._session_id,
                started_at=self._started_at,
                frames_buffered=len(self._frames),
                dropped_frames=self._dropped_frames,
                last_export_path=self._last_export_path,
            )
