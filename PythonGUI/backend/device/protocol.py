from __future__ import annotations

import struct

import numpy as np

from backend.models.frames import BannerPacket, DevicePacket, FramePacket, TextLinePacket

PACKET_MAGIC = b"CCD1"
PACKET_VERSION = 1
PACKET_TYPE_FRAME = 1
MAX_BINARY_SAMPLE_COUNT = 8192
FRAME_HEADER_STRUCT = struct.Struct("<4sBBHIHHHHI")


def parse_device_line(line: str) -> DevicePacket | None:
    """Purpose: classify one decoded text line. Rationale: firmware banners and diagnostics share the same CDC text channel."""
    cleaned = line.strip()
    if not cleaned:
        return None

    if (
        cleaned.startswith("USB CDC")
        or "TIM2_TRGO" in cleaned
        or "ICG-synchronous" in cleaned
        or "TIM4 update=" in cleaned
    ):
        return BannerPacket(text=cleaned)

    return TextLinePacket(text=cleaned)


def encode_raw_command(command_text: str) -> bytes:
    """Purpose: convert a user command into device bytes. Rationale: USB CDC command writes should use one consistent line format."""
    return f"{command_text.strip()}\n".encode("ascii", errors="ignore")


def try_parse_binary_frame(buffer: bytes) -> tuple[FramePacket | None, int]:
    """Purpose: parse one binary frame from a byte buffer. Rationale: packet rebuilding needs both the parsed frame and consumed length."""
    if len(buffer) < FRAME_HEADER_STRUCT.size:
        return None, 0

    (
        magic,
        version,
        packet_type,
        _reserved,
        frame_id,
        sample_count,
        effective_start,
        effective_count,
        flags,
        payload_bytes,
    ) = FRAME_HEADER_STRUCT.unpack_from(buffer)

    if magic != PACKET_MAGIC:
        return None, 1

    if version != PACKET_VERSION or packet_type != PACKET_TYPE_FRAME:
        return None, 1

    if sample_count <= 0 or sample_count > MAX_BINARY_SAMPLE_COUNT:
        return None, 1

    expected_payload_bytes = sample_count * 2
    if payload_bytes != expected_payload_bytes:
        return None, 1

    total_bytes = FRAME_HEADER_STRUCT.size + payload_bytes
    if len(buffer) < total_bytes:
        return None, 0

    payload = memoryview(buffer)[FRAME_HEADER_STRUCT.size:total_bytes]
    adc_counts = np.frombuffer(payload, dtype="<u2", count=sample_count).tolist()

    return (
        FramePacket(
            frame_counter=frame_id,
            sample_count=sample_count,
            effective_start=effective_start,
            effective_count=effective_count,
            flags=flags,
            adc_counts=adc_counts,
        ),
        total_bytes,
    )
