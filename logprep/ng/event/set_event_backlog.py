"""Concrete SetEventBacklog implementation"""

from typing import Iterable

from logprep.ng.abc.event import Event, EventBacklog
from logprep.ng.event.event_state import EventStateType


class SetEventBacklog(EventBacklog):
    """
    A simple event backlog using a Python `set` for storage.

    This backlog stores unique events and allows registration, retrieval,
    and unregistration based on the current processing state of each event.
    """

    def __init__(self) -> None:
        """
        Initialize the internal event backlog as an empty set.
        """

        self.backlog: set[Event] = set()

    def register(self, events: Iterable[Event]) -> None:
        """
        Register one or more events by adding them to the internal backlog set.

        Parameters
        ----------
        events : Iterable[Event]
            An iterable of event instances to be added.
        """

        self.backlog.update(events)

    def unregister(self, state_type: EventStateType) -> set[Event]:
        """
        Unregister all events from the backlog that match the given final state.

        Only `EventStateType.FAILED` and `EventStateType.ACKED` are allowed.
        This check is enforced automatically by the base class.

        Parameters
        ----------
        state_type : EventStateType
            The final state used to filter and remove events.

        Returns
        -------
        set[Event]
            A set of events that were removed from the backlog.
        """

        matching = {event for event in self.backlog if event.state.current_state is state_type}
        self.backlog -= matching

        return matching

    def get(self, state_type: EventStateType) -> set[Event]:
        """
        Retrieve all events from the backlog that match the given processing state.

        Unlike `unregister`, this method does not remove the events from the backlog.

        Parameters
        ----------
        state_type : EventStateType
            The processing state used to filter events.

        Returns
        -------
        set[Event]
            A set of events currently in the backlog that match the given state.
        """

        return {event for event in self.backlog if event.state.current_state is state_type}
