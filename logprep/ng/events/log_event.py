"""Concrete LogEvent implementation and related types."""

from typing import Any

from logprep.ng.abc.event import Event, EventMetadata
from logprep.ng.event_state import EventState, EventStateType


class LogEventState(EventState):
    """
    A specialized EventState used by LogEvent to enforce state transitions
    that depend on the state of associated `extra_data` events.

    This wrapper adds a validation step to prevent transition to `DELIVERED`
    if any related sub-event has not yet reached that state.
    """

    def __init__(self, parent_event: "LogEvent", state: EventState | None = None) -> None:
        """
        Parameters
        ----------
        parent_event : LogEvent
            The event that owns this state object.
        state : EventState, optional
            An optional EventState instance to copy the state from.
        """

        self.parent_event = parent_event

        # use default
        super().__init__()

        # override after init
        if state is not None:
            self.current_state = state.current_state

    def next(self, *, success: bool | None = None) -> EventStateType | None:
        """
        Advances the state, enforcing that `DELIVERED` is only allowed
        when all `extra_data` events have reached the same state.

        Raises
        ------
        ValueError
            If a transition to DELIVERED is attempted but not all
            events in `extra_data` are in DELIVERED state.
        """

        old_state = self.current_state
        new_state = super().next(success=success)

        if new_state == EventStateType.DELIVERED and not all(
            e.state.current_state == EventStateType.DELIVERED for e in self.parent_event.extra_data
        ):
            self.current_state = old_state
            raise ValueError(
                "Cannot assign DELIVERED state: not all extra_data events are DELIVERED."
            )

        return self.current_state


class LogEvent(Event):
    """Concrete log event class with additional attribute and constraints."""

    __slots__: tuple[str, ...] = (
        "original",
        "extra_data",
        "metadata",
        "_state",
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
            Additional associated Event objects.
        metadata : EventMetadata, optional
            Structured metadata for the event.
        state : EventState, optional
            Optional existing EventState to initialize from (e.g. deserialization).

        Examples
        --------
        >>> e1 = Event({"msg": "hello"})
        >>> e2 = Event({"msg": "world"})
        >>> le = LogEvent({"msg": "parent"}, original=b'raw', extra_data=[e1, e2])
        >>> le.original
        b'raw'
        >>> isinstance(le.state, LogEventState)
        True
        """

        self.original = original
        self.extra_data = extra_data if extra_data else []
        self.metadata = metadata

        wrapped_state = LogEventState(parent_event=self, state=state)
        self._state = wrapped_state

        super().__init__(data=data, state=wrapped_state)

    @property
    def state(self) -> EventState:
        """Return the LogEventState instance."""

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

        if value.current_state == EventStateType.DELIVERED:
            if not all(e.state.current_state == EventStateType.DELIVERED for e in self.extra_data):
                raise ValueError(
                    "Cannot assign DELIVERED state: not all extra_data events are DELIVERED."
                )

        self._state.current_state = value.current_state
