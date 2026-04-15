from __future__ import annotations

import re

from backend.models.frames import BannerPacket, DevicePacket, StatusPacket, TextLinePacket

STATUS_LINE_RE = re.compile(
    r"^frame=(?P<frame>\d+)\s+"
    r"samples=(?P<s0>\d+),(?P<s1>\d+),(?P<s2>\d+),(?P<s3>\d+)\s+"
    r"half=(?P<half>\d+)\s+full=(?P<full>\d+)$"
)


def parse_device_line(line: str) -> DevicePacket | None:
    cleaned = line.strip()
    if not cleaned:
        return None

    match = STATUS_LINE_RE.fullmatch(cleaned)
    if match:
        return StatusPacket(
            frame_counter=int(match.group("frame")),
            sample_preview=[
                int(match.group("s0")),
                int(match.group("s1")),
                int(match.group("s2")),
                int(match.group("s3")),
            ],
            dma_half_count=int(match.group("half")),
            dma_full_count=int(match.group("full")),
        )

    if cleaned.startswith("USB CDC") or "TIM2_TRGO" in cleaned:
        return BannerPacket(text=cleaned)

    return TextLinePacket(text=cleaned)


def encode_raw_command(command_text: str) -> bytes:
    return f"{command_text.strip()}\n".encode("ascii", errors="ignore")
