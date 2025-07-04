"""Concrete Log Event implementation"""

from functools import partial
from typing import Any

from logprep.ng.abc.event import Event, EventMetadata
from logprep.ng.event.event_state import EventState, EventStateType


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
        state: EventState | None = None,
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
        state : EventState, optional
            Optional existing EventState to initialize from (e.g. deserialization).

        Examples
        --------
        >>> e1 = Event({"msg": "hello"})
        >>> e2 = Event({"msg": "world"})
        >>> le = LogEvent({"msg": "parent"}, original=b'raw', extra_data=[e1, e2])
        >>> isinstance(le.state, EventState)
        True
        """

        self.original = original
        self.extra_data: list[Event] = extra_data if extra_data else []
        self.metadata = metadata

        super().__init__(data=data, state=state)

        # Wrap original next_state with validation logic
        self._origin_state_next_state_fn = partial(EventState.next_state, self._state)
        setattr(self._state, "next_state", self._next_state_validation_helper)

    def _next_state_validation_helper(
        self, *, success: bool | None = None
    ) -> EventStateType | None:
        new_state: EventStateType = self._origin_state_next_state_fn(success=success)
        self._validate_state(new_state)
        return new_state

    def _validate_state(self, state_type: EventStateType) -> None:
        if state_type == EventStateType.DELIVERED:
            if not all(e.state.current_state == EventStateType.DELIVERED for e in self.extra_data):
                raise ValueError(
                    "Cannot assign DELIVERED state: not all extra_data events are DELIVERED."
                )
