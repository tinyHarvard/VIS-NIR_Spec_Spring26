from __future__ import annotations

import logging
import queue
import threading

from backend.core.session_manager import SessionManager
from backend.core.state_manager import StateManager
from backend.device.base_transport import BaseTransport
from backend.device.packet_reader import DeviceStreamReader
from backend.device.protocol import encode_raw_command
from backend.models.config import CalibrationConfig, UserConfig
from backend.models.frames import BannerPacket, FramePacket, TextLinePacket
from backend.models.status import CommandResult, ConnectionState
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.spectrum_builder import SpectrumBuilder


class CommandService:
    def __init__(
        self,
        *,
        state_manager: StateManager,
        session_manager: SessionManager,
        transport: BaseTransport,
        calibration_manager: CalibrationManager,
        spectrum_builder: SpectrumBuilder,
        logger: logging.Logger | None = None,
    ) -> None:
        self._state_manager = state_manager
        self._session_manager = session_manager
        self._transport = transport
        self._calibration_manager = calibration_manager
        self._spectrum_builder = spectrum_builder
        self._packet_reader = DeviceStreamReader()
        self._last_frame_id: int | None = None
        self._legacy_preview_notice_emitted = False
        self._expected_sample_count = state_manager.get_user_config().device.sample_count
        self._incoming_bytes: queue.Queue[bytes | None] = queue.Queue()
        self._logger = logger or logging.getLogger(__name__)
        self._processor_thread = threading.Thread(
            target=self._processing_loop,
            name="device-packet-processor",
            daemon=True,
        )
        self._processor_thread.start()
        self._transport.set_callbacks(
            on_bytes=self._handle_bytes,
            on_state=self._handle_transport_state,
        )

    def list_serial_ports(self) -> list[dict[str, str]]:
        return self._transport.list_ports()

    def connect(self, port: str | None = None, baudrate: int | None = None) -> CommandResult:
        config = self._state_manager.get_user_config()
        selected_port = port or config.serial.port
        selected_baudrate = int(baudrate or config.serial.baudrate)
        self._packet_reader.reset()
        self._clear_pending_bytes()
        self._last_frame_id = None
        self._legacy_preview_notice_emitted = False

        if not selected_port:
            ports = self.list_serial_ports()
            if not ports:
                return CommandResult(ok=False, message="No serial ports found.")
            selected_port = ports[0]["device"]

        try:
            self._transport.connect(
                port=selected_port,
                baudrate=selected_baudrate,
                timeout_s=config.serial.timeout_s,
            )
        except Exception as exc:
            self._logger.exception("Failed to connect to serial device.")
            self._state_manager.set_connection_state(
                ConnectionState.error,
                port=selected_port,
                baudrate=selected_baudrate,
                error=str(exc),
                message="Connection failed.",
            )
            self._state_manager.append_log(f"Connection failed: {exc}")
            return CommandResult(ok=False, message=str(exc))

        config.serial.port = selected_port
        config.serial.baudrate = selected_baudrate
        self._state_manager.set_user_config(config)
        self._state_manager.set_connection_state(
            ConnectionState.connected,
            port=selected_port,
            baudrate=selected_baudrate,
            message=f"Connected to {selected_port}.",
        )
        self._state_manager.reset_frame_tracking()
        self._state_manager.append_log(
            f"Connected to {selected_port} at {selected_baudrate} baud."
        )
        return CommandResult(ok=True, message=f"Connected to {selected_port}.")

    def disconnect(self) -> CommandResult:
        self._transport.disconnect()
        self._packet_reader.reset()
        self._clear_pending_bytes()
        self._last_frame_id = None
        self._legacy_preview_notice_emitted = False
        self._state_manager.reset_frame_tracking()
        self._state_manager.set_connection_state(
            ConnectionState.disconnected,
            message="Disconnected.",
        )
        self._state_manager.append_log("Disconnected from spectrometer.")
        return CommandResult(ok=True, message="Disconnected.")

    def send_raw_command(self, command_text: str) -> CommandResult:
        cleaned = command_text.strip()
        if not cleaned:
            return CommandResult(ok=False, message="Command text is empty.")

        if not self._transport.is_connected():
            return CommandResult(ok=False, message="Device is not connected.")

        self._transport.write(encode_raw_command(cleaned))
        self._state_manager.append_log(f"TX > {cleaned}")
        return CommandResult(
            ok=True,
            message=(
                "Command sent over USB CDC. The current STM32 firmware does not yet "
                "parse incoming CDC commands, so this is future-ready plumbing."
            ),
        )

    def apply_user_config(self, config: UserConfig) -> None:
        self._state_manager.set_user_config(config)
        self._spectrum_builder.update_device_config(config.device)
        self._session_manager.set_max_frames(config.ui.max_session_frames)
        self._expected_sample_count = config.device.sample_count
        self._state_manager.set_session_status(self._session_manager.status())
        self._state_manager.append_log("User configuration updated.")

    def apply_calibration_config(self, config: CalibrationConfig) -> None:
        self._calibration_manager.update_config(config)
        self._state_manager.set_calibration_config(config)
        self._state_manager.append_log("Calibration configuration updated.")

    def refresh_session_status(self) -> None:
        self._state_manager.set_session_status(self._session_manager.status())

    def _handle_transport_state(self, state: ConnectionState, detail: str | None) -> None:
        if state == ConnectionState.error:
            self._state_manager.set_connection_state(
                ConnectionState.error,
                error=detail,
                message=detail,
            )
            if detail:
                self._state_manager.append_log(f"Transport error: {detail}")
            return

        if state == ConnectionState.disconnected:
            self._last_frame_id = None

        self._state_manager.set_connection_state(state, message=detail)
        if detail:
            self._state_manager.append_log(detail)

    def _handle_bytes(self, data: bytes) -> None:
        if data:
            self._incoming_bytes.put_nowait(bytes(data))

    def _processing_loop(self) -> None:
        while True:
            data = self._incoming_bytes.get()
            if data is None:
                return
            for packet in self._packet_reader.feed(data):
                self._process_packet(packet)

    def _process_packet(self, packet: BannerPacket | TextLinePacket | FramePacket) -> None:
        if isinstance(packet, BannerPacket):
            self._state_manager.add_firmware_message(packet.text)
            self._state_manager.append_log(packet.text)
            return

        if isinstance(packet, TextLinePacket):
            self._state_manager.append_log(packet.text)
            return

        if isinstance(packet, FramePacket):
            if (
                packet.sample_count < self._expected_sample_count
                and not self._legacy_preview_notice_emitted
            ):
                self._legacy_preview_notice_emitted = True
                self._state_manager.append_log(
                    "Detected a legacy preview stream from the STM32: "
                    f"received {packet.sample_count} samples, expected {self._expected_sample_count}. "
                    "Flash the updated full-frame firmware to view the full CCD line."
                )

            missed_frames = 0
            if self._last_frame_id is not None and packet.frame_counter > self._last_frame_id + 1:
                missed_frames = packet.frame_counter - self._last_frame_id - 1
                self._state_manager.append_log(
                    f"Missed {missed_frames} frame(s) before frame {packet.frame_counter}."
                )

            self._last_frame_id = packet.frame_counter
            self._state_manager.update_from_frame_packet(packet, missed_frames=missed_frames)
            spectrum = self._spectrum_builder.build_from_frame_packet(packet)
            self._state_manager.set_last_spectrum(spectrum)
            self._session_manager.append_frame(spectrum)
            self._state_manager.set_session_status(self._session_manager.status())

    def _clear_pending_bytes(self) -> None:
        while True:
            try:
                pending = self._incoming_bytes.get_nowait()
            except queue.Empty:
                return
            if pending is None:
                self._incoming_bytes.put_nowait(None)
                return
