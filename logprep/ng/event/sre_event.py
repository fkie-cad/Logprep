"""Concrete Sre Event implementation"""

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState


class SreEvent(Event):
    """Concrete Sre event class."""

    __slots__ = ("outputs",)

    outputs: tuple[dict[str, str]]

    def __init__(
        self, data: dict[str, str], *, outputs: tuple[dict], state: EventState | None = None
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
        self.outputs = outputs
        super().__init__(data=data, state=state)
