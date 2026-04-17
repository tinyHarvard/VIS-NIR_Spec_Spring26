from __future__ import annotations

import threading

import serial
from serial.tools import list_ports

from backend.device.base_transport import BaseTransport
from backend.models.status import ConnectionState


class SerialTransport(BaseTransport):
    """Purpose: implement USB serial communication. Rationale: pyserial details should stay isolated from the rest of the app."""
    def __init__(self) -> None:
        """Purpose: initialize serial transport state. Rationale: the reader thread, port handle, and locks need one owner."""
        super().__init__()
        self._serial: serial.Serial | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()

    def connect(
        self,
        *,
        port: str | None = None,
        baudrate: int = 115200,
        timeout_s: float = 0.1,
    ) -> None:
        """Purpose: open the selected COM port and start reading. Rationale: connection startup should also launch the background reader."""
        if self.is_connected():
            self.disconnect()

        selected_port = port
        if not selected_port:
            ports = self.list_ports()
            if not ports:
                raise RuntimeError("No serial ports found.")
            selected_port = ports[0]["device"]

        self._emit_state(ConnectionState.connecting, f"Opening {selected_port}...")
        self._serial = serial.Serial(
            port=selected_port,
            baudrate=baudrate,
            timeout=timeout_s,
        )
        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="serial-reader",
            daemon=True,
        )
        self._reader_thread.start()
        self._emit_state(ConnectionState.connected, f"Connected to {selected_port}.")

    def disconnect(self) -> None:
        """Purpose: stop the reader thread and close the port. Rationale: shutdown should release the OS handle cleanly."""
        self._stop_event.set()

        serial_handle = self._serial
        self._serial = None
        if serial_handle is not None and serial_handle.is_open:
            serial_handle.close()

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=0.5)
            self._reader_thread = None

        self._emit_state(ConnectionState.disconnected, "Serial connection closed.")

    def write(self, payload: bytes) -> None:
        """Purpose: send bytes over the serial port. Rationale: writes should be synchronized so commands are not interleaved."""
        if not self.is_connected() or self._serial is None:
            raise RuntimeError("Serial transport is not connected.")

        with self._write_lock:
            self._serial.write(payload)
            self._serial.flush()

    def is_connected(self) -> bool:
        """Purpose: report whether the serial port is open. Rationale: callers need a quick readiness check before reading or writing."""
        return self._serial is not None and self._serial.is_open

    def list_ports(self) -> list[dict[str, str]]:
        """Purpose: enumerate available COM ports. Rationale: the UI needs human-readable choices for connection selection."""
        available = []
        for port in sorted(list_ports.comports(), key=lambda item: item.device):
            available.append(
                {
                    "device": port.device,
                    "description": port.description or "",
                    "hwid": port.hwid or "",
                }
            )
        return available

    def _reader_loop(self) -> None:
        """Purpose: continuously read serial bytes in the background. Rationale: incoming data should be collected without blocking the UI."""
        try:
            while not self._stop_event.is_set():
                serial_handle = self._serial
                if serial_handle is None or not serial_handle.is_open:
                    break

                chunk = serial_handle.read(max(1, serial_handle.in_waiting or 1))
                if chunk:
                    self._emit_bytes(chunk)
        except serial.SerialException as exc:
            if not self._stop_event.is_set():
                self._emit_state(ConnectionState.error, str(exc))
        finally:
            if not self._stop_event.is_set():
                self._emit_state(ConnectionState.disconnected, "Serial reader stopped.")
