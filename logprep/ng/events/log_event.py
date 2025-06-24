"""Concrete Log Event implementation"""

from types import MethodType
from typing import Any

from logprep.ng.abc.event import Event, EventMetadata
from logprep.ng.event_state import EventState, EventStateType


class LogEvent(Event):
    """Concrete log event class with additional attribute and constraints."""

    __slots__: tuple[str, ...] = (
        "original",
        "extra_data",
        "metadata",
        "_state",
        "_origin_state_next_state_fn",
    )

    def __init__(  # pylint: disable=too-many-arguments
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
        self.extra_data = extra_data if extra_data else []
        self.metadata = metadata

        self._state: EventState = EventState() if state is None else state

        super().__init__(data=data, state=self._state)

        # Wrap original next_state with validation logic
        self._origin_state_next_state_fn = MethodType(EventState.next_state, self._state)
        self._state.next_state = self._next_state_validation_helper

    @property
    def state(self) -> EventState:
        """Return the current EventState instance."""

        return self._state

    @state.setter
    def state(self, value: EventState) -> None:
        """
        Prevent assignment of a DELIVERED state if not all extra_data events are DELIVERED.

        Parameters
        ----------
        value : EventState
            The state to assign.

        Raises
        ------
        ValueError
            If value.state is DELIVERED but any sub-event is not DELIVERED.
        """
        self._validate_state(value.current_state)
        self._state = value

        # Wrap next_state again if needed
        self._origin_state_next_state_fn = self._state.next_state
        self._state.next_state = self._next_state_validation_helper

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
