from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from backend.models.config import CalibrationConfig, UserConfig
from backend.models.frames import SpectrumFrame, StatusPacket
from backend.models.status import AppSnapshot, ConnectionState, DeviceStatus, SessionStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StateManager:
    def __init__(
        self,
        user_config: UserConfig,
        calibration_config: CalibrationConfig,
        *,
        max_logs: int = 250,
    ) -> None:
        self._lock = Lock()
        self._user_config = user_config
        self._calibration_config = calibration_config
        self._device_status = DeviceStatus()
        self._session_status = SessionStatus(session_id=self.new_session_id())
        self._last_spectrum: SpectrumFrame | None = None
        self._logs: deque[str] = deque(maxlen=max_logs)

    @staticmethod
    def new_session_id() -> str:
        return uuid4().hex[:8]

    def get_user_config(self) -> UserConfig:
        with self._lock:
            return self._user_config.model_copy(deep=True)

    def set_user_config(self, user_config: UserConfig) -> None:
        with self._lock:
            self._user_config = user_config

    def get_calibration_config(self) -> CalibrationConfig:
        with self._lock:
            return self._calibration_config.model_copy(deep=True)

    def set_calibration_config(self, calibration_config: CalibrationConfig) -> None:
        with self._lock:
            self._calibration_config = calibration_config

    def set_connection_state(
        self,
        state: ConnectionState,
        *,
        port: str | None = None,
        baudrate: int | None = None,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._device_status.connection_state = state
            if port is not None:
                self._device_status.port = port
            if baudrate is not None:
                self._device_status.baudrate = baudrate
            if message is not None:
                self._device_status.last_message = message
            if error is not None:
                self._device_status.last_error = error
            elif state != ConnectionState.error:
                self._device_status.last_error = None

    def add_firmware_message(self, text: str) -> None:
        with self._lock:
            self._device_status.firmware_messages.append(text)
            self._device_status.firmware_messages = self._device_status.firmware_messages[-10:]
            self._device_status.last_message = text

    def append_log(self, text: str) -> None:
        timestamp = utc_now().strftime("%H:%M:%S")
        with self._lock:
            self._logs.append(f"[{timestamp}] {text}")

    def update_from_status_packet(self, packet: StatusPacket) -> None:
        with self._lock:
            self._device_status.last_seen = packet.timestamp
            self._device_status.frame_counter = packet.frame_counter
            self._device_status.dma_half_count = packet.dma_half_count
            self._device_status.dma_full_count = packet.dma_full_count
            self._device_status.sample_preview = list(packet.sample_preview)
            self._device_status.last_message = f"Frame {packet.frame_counter} received."

    def set_last_spectrum(self, frame: SpectrumFrame) -> None:
        with self._lock:
            self._last_spectrum = frame

    def set_session_status(self, session_status: SessionStatus) -> None:
        with self._lock:
            self._session_status = session_status

    def snapshot(self) -> AppSnapshot:
        with self._lock:
            return AppSnapshot(
                device=self._device_status.model_copy(deep=True),
                session=self._session_status.model_copy(deep=True),
                spectrum=self._last_spectrum.model_copy(deep=True)
                if self._last_spectrum is not None
                else None,
                logs=list(self._logs),
            )
