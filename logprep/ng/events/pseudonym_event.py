"""Concrete Pseudonym Event implementation"""

from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState


class PseudonymEvent(Event):
    """Concrete Pseudonym event class."""

    __slots__: tuple[str, ...] = ("_state",)

    def __init__(
        self,
        data: dict[str, Any],
        *,
        state: EventState | None = None,
    ) -> None:
        """
        Parameters
        ----------
        data : dict[str, Any]
            The main data payload for the event.
        state : EventState, optional
            Optional existing EventState to initialize from (e.g. deserialization).

        Examples
        --------
        >>> e1 = Event({"msg": "hello"})
        >>> e2 = Event({"msg": "world"})
        >>> le = PseudonymEvent({"msg": "parent"})
        >>> isinstance(le.state, EventState)
        True
        """

        self._state: EventState = EventState() if state is None else state
        super().__init__(data=data, state=self._state)

    @property
    def state(self) -> EventState:
        """Return the current EventState instance."""
        return self._state

    @state.setter
    def state(self, value: EventState) -> None:
        """
        Assigns a new EventState.
        """
        self._state = value
