from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from backend.models.status import ConnectionState

BytesCallback = Callable[[bytes], None]
StateCallback = Callable[[ConnectionState, str | None], None]


class BaseTransport(ABC):
    def __init__(self) -> None:
        self._on_bytes: BytesCallback | None = None
        self._on_state: StateCallback | None = None

    def set_callbacks(
        self,
        on_bytes: BytesCallback | None = None,
        on_state: StateCallback | None = None,
    ) -> None:
        self._on_bytes = on_bytes
        self._on_state = on_state

    def _emit_bytes(self, data: bytes) -> None:
        if self._on_bytes is not None:
            self._on_bytes(data)

    def _emit_state(self, state: ConnectionState, detail: str | None = None) -> None:
        if self._on_state is not None:
            self._on_state(state, detail)

    @abstractmethod
    def connect(self, **kwargs: object) -> None:
        """Open the transport."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the transport."""

    @abstractmethod
    def write(self, payload: bytes) -> None:
        """Write bytes to the device."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True when the transport is open."""

    @abstractmethod
    def list_ports(self) -> list[dict[str, str]]:
        """Return currently available connection targets."""
