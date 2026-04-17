from __future__ import annotations

from backend.device.base_transport import BaseTransport


class WifiTransport(BaseTransport):
    def connect(self, **kwargs: object) -> None:
        """Purpose: reserve a future WiFi connect API. Rationale: transport abstraction is ready even though WiFi is not yet implemented."""
        raise NotImplementedError("WiFi transport is not implemented yet.")

    def disconnect(self) -> None:
        """Purpose: provide a no-op disconnect for the placeholder transport. Rationale: unimplemented transports should still satisfy the interface."""
        return None

    def write(self, payload: bytes) -> None:
        """Purpose: reserve a future WiFi write API. Rationale: command routing can stay transport-agnostic as features expand."""
        raise NotImplementedError("WiFi transport is not implemented yet.")

    def is_connected(self) -> bool:
        """Purpose: report placeholder connection state. Rationale: callers should get a safe false result until WiFi exists."""
        return False

    def list_ports(self) -> list[dict[str, str]]:
        """Purpose: return placeholder connection targets. Rationale: WiFi discovery is not implemented yet, so no targets are exposed."""
        return []
