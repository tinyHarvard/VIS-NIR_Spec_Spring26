from __future__ import annotations


class LinePacketReader:
    """Rebuild newline-delimited USB CDC text packets from arbitrary byte chunks."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[str]:
        self._buffer.extend(data)
        lines: list[str] = []

        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                break

            raw_line = bytes(self._buffer[:newline_index]).rstrip(b"\r")
            del self._buffer[: newline_index + 1]
            lines.append(raw_line.decode("utf-8", errors="replace"))

        return lines

    def reset(self) -> None:
        self._buffer.clear()
