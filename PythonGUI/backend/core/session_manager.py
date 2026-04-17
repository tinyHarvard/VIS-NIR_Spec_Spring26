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
    """Purpose: return the current UTC time. Rationale: session timestamps should use one shared helper."""
    return datetime.now(timezone.utc)


class SessionManager:
    """Purpose: manage the rolling frame buffer and exports. Rationale: capture history should be separate from live state."""
    def __init__(
        self,
        export_dir: Path,
        *,
        max_frames: int = 2000,
        spectrum_builder: "SpectrumBuilder | None" = None,
    ) -> None:
        """Purpose: initialize the session buffer and metadata. Rationale: exporting needs a stable owner for captured frames."""
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
        """Purpose: create a short unique session label. Rationale: saved sessions should be easy to identify."""
        return uuid4().hex[:8]

    def set_max_frames(self, max_frames: int) -> None:
        """Purpose: resize the rolling frame buffer. Rationale: buffer depth may change without discarding the newest useful data."""
        with self._lock:
            current_frames = list(self._frames)[-max_frames:]
            if len(self._frames) > max_frames:
                self._dropped_frames += len(self._frames) - max_frames
            self._max_frames = max_frames
            self._frames = deque(current_frames, maxlen=max_frames)

    def append_frame(self, frame: SpectrumFrame) -> None:
        """Purpose: add one frame to the session buffer. Rationale: capture history should roll forward automatically during streaming."""
        with self._lock:
            if len(self._frames) == self._frames.maxlen:
                self._dropped_frames += 1
            self._frames.append(frame)

    def set_spectrum_builder(self, spectrum_builder: "SpectrumBuilder") -> None:
        """Purpose: store the export-time processing helper. Rationale: CSV export may need derived columns built on demand."""
        with self._lock:
            self._spectrum_builder = spectrum_builder

    def reset(self) -> None:
        """Purpose: clear the buffered session. Rationale: the user may want a fresh capture without restarting the app."""
        with self._lock:
            self._frames.clear()
            self._session_id = self._new_session_id()
            self._started_at = utc_now()
            self._dropped_frames = 0
            self._last_export_path = None

    def export_csv(self) -> Path:
        """Purpose: write the buffered session to CSV. Rationale: captured data should be easy to inspect outside the app."""
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
        """Purpose: return buffered frames. Rationale: callers should get a copy rather than direct access to the deque."""
        with self._lock:
            return list(self._frames)

    def status(self) -> SessionStatus:
        """Purpose: summarize the current session buffer. Rationale: the UI needs lightweight session metadata during refresh."""
        with self._lock:
            return SessionStatus(
                session_id=self._session_id,
                started_at=self._started_at,
                frames_buffered=len(self._frames),
                dropped_frames=self._dropped_frames,
                last_export_path=self._last_export_path,
            )
