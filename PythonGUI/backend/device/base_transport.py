from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from backend.models.status import ConnectionState

BytesCallback = Callable[[bytes], None]
StateCallback = Callable[[ConnectionState, str | None], None]


class BaseTransport(ABC):
    """Purpose: define the shared transport interface. Rationale: higher layers should work with serial or future transports uniformly."""
    def __init__(self) -> None:
        """Purpose: initialize callback storage. Rationale: transports need a consistent way to emit bytes and state changes."""
        self._on_bytes: BytesCallback | None = None
        self._on_state: StateCallback | None = None

    def set_callbacks(
        self,
        on_bytes: BytesCallback | None = None,
        on_state: StateCallback | None = None,
    ) -> None:
        """Purpose: register byte and state callbacks. Rationale: the transport should push events instead of being polled manually."""
        self._on_bytes = on_bytes
        self._on_state = on_state

    def _emit_bytes(self, data: bytes) -> None:
        """Purpose: forward received bytes to the callback. Rationale: subclasses should share one safe emit path."""
        if self._on_bytes is not None:
            self._on_bytes(data)

    def _emit_state(self, state: ConnectionState, detail: str | None = None) -> None:
        """Purpose: forward a connection-state change. Rationale: subclasses should report state transitions the same way."""
        if self._on_state is not None:
            self._on_state(state, detail)

    @abstractmethod
    def connect(self, **kwargs: object) -> None:
        """Purpose: open the transport. Rationale: every concrete transport must expose a common connect operation."""

    @abstractmethod
    def disconnect(self) -> None:
        """Purpose: close the transport. Rationale: every concrete transport must expose a common disconnect operation."""

    @abstractmethod
    def write(self, payload: bytes) -> None:
        """Purpose: send bytes to the device. Rationale: command paths should not care which transport implementation is active."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Purpose: report whether the transport is open. Rationale: callers need one transport-agnostic readiness check."""

    @abstractmethod
    def list_ports(self) -> list[dict[str, str]]:
        """Purpose: enumerate available connection targets. Rationale: the UI needs a generic way to populate connection choices."""
