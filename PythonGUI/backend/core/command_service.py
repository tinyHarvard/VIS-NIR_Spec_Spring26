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
    """Purpose: coordinate transport, parsing, state updates, and user commands. Rationale: one service keeps the data path organized."""
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
        """Purpose: wire the command layer to its dependencies. Rationale: incoming device data and UI actions share one coordinator."""
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
        """Purpose: return visible serial ports. Rationale: the UI should ask the service, not the transport, directly."""
        return self._transport.list_ports()

    def connect(self, port: str | None = None) -> CommandResult:
        """Purpose: open the device connection. Rationale: connect logic must reset parser state and update app status consistently."""
        config = self._state_manager.get_user_config()
        selected_port = port or config.serial.port
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
                timeout_s=config.serial.timeout_s,
            )
        except Exception as exc:
            self._logger.exception("Failed to connect to serial device.")
            self._state_manager.set_connection_state(
                ConnectionState.error,
                port=selected_port,
                error=str(exc),
                message="Connection failed.",
            )
            self._state_manager.append_log(f"Connection failed: {exc}")
            return CommandResult(ok=False, message=str(exc))

        config.serial.port = selected_port
        self._state_manager.set_user_config(config)
        self._state_manager.set_connection_state(
            ConnectionState.connected,
            port=selected_port,
            message=f"Connected to {selected_port}.",
        )
        self._state_manager.reset_frame_tracking()
        self._state_manager.append_log(f"Connected to {selected_port}.")
        return CommandResult(ok=True, message=f"Connected to {selected_port}.")

    def disconnect(self) -> CommandResult:
        """Purpose: close the device connection and clear live frame state. Rationale: disconnects should leave the app in a clean state."""
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
        """Purpose: send a text command to the device. Rationale: command writes should use the same service path as other actions."""
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
        """Purpose: apply new user settings to the running app. Rationale: config edits should immediately update dependent services."""
        self._state_manager.set_user_config(config)
        self._spectrum_builder.update_device_config(config.device)
        self._session_manager.set_max_frames(config.ui.max_session_frames)
        self._expected_sample_count = config.device.sample_count
        self._state_manager.set_session_status(self._session_manager.status())
        self._state_manager.append_log("User configuration updated.")

    def apply_calibration_config(self, config: CalibrationConfig) -> None:
        """Purpose: apply new calibration settings. Rationale: calibration changes should flow through one controlled update point."""
        self._calibration_manager.update_config(config)
        self._state_manager.set_calibration_config(config)
        latest_spectrum = self._state_manager.latest_spectrum()
        if latest_spectrum is not None:
            self._state_manager.set_last_spectrum(
                self._spectrum_builder.rebuild_live_frame(latest_spectrum)
            )
        self._state_manager.append_log("Calibration configuration updated.")

    def refresh_session_status(self) -> None:
        """Purpose: push the latest session summary into shared state. Rationale: UI reads should come from StateManager snapshots."""
        self._state_manager.set_session_status(self._session_manager.status())

    def _handle_transport_state(self, state: ConnectionState, detail: str | None) -> None:
        """Purpose: mirror transport state changes into app state. Rationale: the UI should react to connection events consistently."""
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
        """Purpose: enqueue raw device bytes. Rationale: the serial reader thread should stay light and avoid heavy parsing work."""
        if data:
            self._incoming_bytes.put_nowait(bytes(data))

    def _processing_loop(self) -> None:
        """Purpose: turn queued bytes into packets on a worker thread. Rationale: parsing and frame handling should not block serial reads."""
        while True:
            data = self._incoming_bytes.get()
            if data is None:
                return
            for packet in self._packet_reader.feed(data):
                self._process_packet(packet)

    def _process_packet(self, packet: BannerPacket | TextLinePacket | FramePacket) -> None:
        """Purpose: apply one parsed packet to the app state. Rationale: each packet type affects the app differently but through one path."""
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
        """Purpose: empty the queued raw-byte backlog. Rationale: reconnects should not process stale bytes from an old session."""
        while True:
            try:
                pending = self._incoming_bytes.get_nowait()
            except queue.Empty:
                return
            if pending is None:
                self._incoming_bytes.put_nowait(None)
                return
