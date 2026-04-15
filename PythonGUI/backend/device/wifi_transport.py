from __future__ import annotations

from backend.device.base_transport import BaseTransport


class WifiTransport(BaseTransport):
    def connect(self, **kwargs: object) -> None:
        raise NotImplementedError("WiFi transport is not implemented yet.")

    def disconnect(self) -> None:
        return None

    def write(self, payload: bytes) -> None:
        raise NotImplementedError("WiFi transport is not implemented yet.")

    def is_connected(self) -> bool:
        return False

    def list_ports(self) -> list[dict[str, str]]:
        return []
