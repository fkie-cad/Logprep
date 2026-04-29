"""Concrete Log Event implementation"""

from typing import Any

from logprep.ng.abc.event import Event, EventMetadata


class LogEvent(Event):
    """Concrete log event class with additional attribute and constraints."""

    __slots__: tuple[str, ...] = (
        "original",
        "extra_data",
        "metadata",
        "_origin_state_next_state_fn",
    )

    def __init__(
        self,
        data: dict[str, Any],
        *,
        original: bytes,
        extra_data: list[Event] | None = None,
        metadata: EventMetadata | None = None,
    ) -> None:
        """
        Parameters
        ----------
        data : dict[str, Any]
            The main data payload for the event.
        original : bytes
            The raw representation of the event (e.g., as received from Kafka).
        extra_data : list[Event], optional
            Sub-events that were derived or caused by this event
        metadata : EventMetadata, optional
            Structured metadata for the event.
        """

        self.original = original
        self.extra_data: list[Event] = extra_data if extra_data else []
        self.metadata = metadata

        super().__init__(data=data)
