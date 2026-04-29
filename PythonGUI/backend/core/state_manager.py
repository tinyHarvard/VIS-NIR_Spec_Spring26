from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from backend.models.config import CalibrationConfig, UserConfig
from backend.models.frames import FramePacket, SpectrumFrame
from backend.models.status import AppSnapshot, ConnectionState, DeviceStatus, SessionStatus


def utc_now() -> datetime:
    """Purpose: return the current UTC time. Rationale: timestamp formatting should stay consistent inside the state layer."""
    return datetime.now(timezone.utc)


class StateManager:
    """Purpose: own the app's current live state. Rationale: UI and worker threads need one synchronized source of truth."""
    def __init__(
        self,
        user_config: UserConfig,
        calibration_config: CalibrationConfig,
        *,
        max_logs: int = 250,
    ) -> None:
        """Purpose: initialize configs, status objects, and logs. Rationale: the app should start from a complete known state."""
        self._lock = Lock()
        self._user_config = user_config
        self._calibration_config = calibration_config
        self._device_status = DeviceStatus(
            sample_count=user_config.device.sample_count,
            effective_start_index=user_config.device.effective_start_index,
            effective_sample_count=user_config.device.effective_sample_count,
        )
        self._session_status = SessionStatus(session_id=self.new_session_id())
        self._last_spectrum: SpectrumFrame | None = None
        self._logs: deque[str] = deque(maxlen=max_logs)

    @staticmethod
    def new_session_id() -> str:
        """Purpose: create a short random session identifier. Rationale: session labels should be unique but easy to read."""
        return uuid4().hex[:8]

    def get_user_config(self) -> UserConfig:
        """Purpose: return the current user config. Rationale: callers should read a safe copy instead of mutating shared state."""
        with self._lock:
            return self._user_config.model_copy(deep=True)

    def set_user_config(self, user_config: UserConfig) -> None:
        """Purpose: store new user settings. Rationale: config changes should immediately update matching live device expectations."""
        with self._lock:
            self._user_config = user_config
            self._device_status.sample_count = user_config.device.sample_count
            self._device_status.effective_start_index = user_config.device.effective_start_index
            self._device_status.effective_sample_count = user_config.device.effective_sample_count

    def get_calibration_config(self) -> CalibrationConfig:
        """Purpose: return the current calibration config. Rationale: readers should not directly mutate the shared object."""
        with self._lock:
            return self._calibration_config.model_copy(deep=True)

    def set_calibration_config(self, calibration_config: CalibrationConfig) -> None:
        """Purpose: store new calibration settings. Rationale: calibration state needs one synchronized owner."""
        with self._lock:
            self._calibration_config = calibration_config

    def set_connection_state(
        self,
        state: ConnectionState,
        *,
        port: str | None = None,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        """Purpose: update connection-related fields. Rationale: transport state changes should land in one consistent place."""
        with self._lock:
            self._device_status.connection_state = state
            if port is not None:
                self._device_status.port = port
            if message is not None:
                self._device_status.last_message = message
            if error is not None:
                self._device_status.last_error = error
            elif state != ConnectionState.error:
                self._device_status.last_error = None

    def add_firmware_message(self, text: str) -> None:
        """Purpose: remember recent firmware banner text. Rationale: startup messages help the user confirm what firmware is running."""
        with self._lock:
            self._device_status.firmware_messages.append(text)
            self._device_status.firmware_messages = self._device_status.firmware_messages[-10:]
            self._device_status.last_message = text

    def append_log(self, text: str) -> None:
        """Purpose: add a timestamped log entry. Rationale: lightweight diagnostics should be visible inside the app."""
        timestamp = utc_now().strftime("%H:%M:%S")
        with self._lock:
            self._logs.append(f"[{timestamp}] {text}")

    def reset_frame_tracking(self) -> None:
        """Purpose: clear frame-specific live state. Rationale: reconnects should not reuse stale frame counters or spectra."""
        with self._lock:
            self._device_status.frame_counter = 0
            self._device_status.sample_count = self._user_config.device.sample_count
            self._device_status.effective_start_index = self._user_config.device.effective_start_index
            self._device_status.effective_sample_count = self._user_config.device.effective_sample_count
            self._device_status.missed_frames = 0
            self._device_status.last_frame_flags = 0
            self._device_status.sample_preview = []
            self._last_spectrum = None

    def update_from_frame(self, frame: FramePacket, *, missed_frames: int = 0) -> None:
        """Purpose: copy new frame metadata into live status. Rationale: the UI should read frame summaries without parsing frames itself."""
        with self._lock:
            self._device_status.last_seen = frame.timestamp
            self._device_status.frame_counter = frame.frame_counter
            self._device_status.sample_count = frame.sample_count
            self._device_status.effective_start_index = frame.effective_start
            self._device_status.effective_sample_count = frame.effective_count
            self._device_status.last_frame_flags = frame.flags
            self._device_status.missed_frames += missed_frames
            self._device_status.sample_preview = (
                list(frame.adc_counts[:4]) + list(frame.adc_counts[-4:])
                if len(frame.adc_counts) >= 8
                else list(frame.adc_counts)
            )
            self._device_status.last_message = f"Frame {frame.frame_counter} received."

    def set_last_spectrum(self, frame: SpectrumFrame) -> None:
        """Purpose: store the newest spectrum frame. Rationale: the plot should always have a single latest frame to display."""
        with self._lock:
            self._last_spectrum = frame

    def latest_spectrum(self) -> SpectrumFrame | None:
        """Purpose: return the newest stored spectrum. Rationale: the fast plot path should avoid rebuilding full snapshots."""
        with self._lock:
            return self._last_spectrum

    def set_session_status(self, session_status: SessionStatus) -> None:
        """Purpose: store the latest session summary. Rationale: session tracking is updated by other services and displayed by the UI."""
        with self._lock:
            self._session_status = session_status

    def snapshot(self, *, include_spectrum: bool = True) -> AppSnapshot:
        """Purpose: return a combined app-state snapshot. Rationale: grouped reads reduce lock churn and simplify UI refreshes."""
        with self._lock:
            return AppSnapshot(
                device=self._device_status.model_copy(deep=True),
                session=self._session_status.model_copy(deep=True),
                spectrum=self._last_spectrum.model_copy(deep=True)
                if include_spectrum and self._last_spectrum is not None
                else None,
                logs=list(self._logs),
            )
