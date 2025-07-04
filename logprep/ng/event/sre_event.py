"""Concrete Sre Event implementation"""

from typing import Iterable

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState


class SreEvent(Event):
    """Concrete Sre event class."""

    __slots__ = ("outputs",)

    outputs: list[str]

    def __init__(
        self, data: dict[str, str], *, outputs: Iterable[str], state: EventState | None = None
    ) -> None:
        """
        Parameters
        ----------
        data : dict[str, str]
            The main data payload for the SRE event.
        state : EventState
            The state of the SRE event.
        outputs : Iterable[str]
            The collection of output connector names associated with the SRE event
        """
        self.outputs = list(outputs)
        super().__init__(data=data, state=state)
