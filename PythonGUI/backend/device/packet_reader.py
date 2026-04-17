from __future__ import annotations

from backend.device.protocol import PACKET_MAGIC, parse_device_line, try_parse_binary_frame
from backend.models.frames import DevicePacket


class DeviceStreamReader:
    """Rebuild mixed ASCII banners and binary CCD frame packets from USB CDC bytes."""

    def __init__(self) -> None:
        """Purpose: initialize the incoming byte buffer. Rationale: serial reads may split packets across many chunks."""
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[DevicePacket]:
        """Purpose: parse complete packets from new bytes. Rationale: the device stream mixes binary frames and text lines."""
        self._buffer.extend(data)
        packets: list[DevicePacket] = []

        while True:
            if self._buffer.startswith(PACKET_MAGIC):
                packet, consumed = try_parse_binary_frame(self._buffer)
                if consumed == 0:
                    break
                if packet is not None:
                    packets.append(packet)
                del self._buffer[:consumed]
                continue

            newline_index = self._buffer.find(b"\n")
            magic_index = self._buffer.find(PACKET_MAGIC)

            if newline_index >= 0 and (magic_index < 0 or newline_index < magic_index):
                raw_line = bytes(self._buffer[:newline_index]).rstrip(b"\r")
                del self._buffer[: newline_index + 1]
                packet = parse_device_line(raw_line.decode("utf-8", errors="replace"))
                if packet is not None:
                    packets.append(packet)
                continue

            if magic_index > 0:
                prefix = bytes(self._buffer[:magic_index]).replace(b"\x00", b"").strip()
                del self._buffer[:magic_index]
                if prefix:
                    packet = parse_device_line(prefix.decode("utf-8", errors="replace"))
                    if packet is not None:
                        packets.append(packet)
                continue

            if newline_index < 0 and magic_index < 0:
                if len(self._buffer) > FRAME_HEADER_LIMIT:
                    del self._buffer[:-3]
                break
            break

        return packets

    def reset(self) -> None:
        """Purpose: clear the internal parse buffer. Rationale: reconnects should not reuse leftover bytes from old sessions."""
        self._buffer.clear()


FRAME_HEADER_LIMIT = 1024
