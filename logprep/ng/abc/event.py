# pylint: disable=too-few-public-methods
# -> deactivate temporarily pylint issue here

"""abstract module for event"""

from abc import ABC
from typing import Any

from logprep.ng.event_state import EventState


class EventMetadata(ABC):
    """Abstract EventMetadata Class to define the Interface"""


class Event(ABC):
    """
    Abstract base class representing an event in the processing pipeline.

    This class encapsulates event-related data, warnings, errors,
    and its current processing state via a state machine.

    Parameters
    ----------
    data : dict[str, Any]
        The raw or processed data associated with the event.
    state : EventState, optional (keyword-only)
        The initial state of the event. If not provided, defaults to `EventState()`.

    Attributes
    ----------
    data : dict[str, Any]
        The actual payload or metadata of the event.
    state : EventState
        Tracks the current state of the event lifecycle.
    warnings : list[Any]
        Collected warnings during event handling or transformation.
    errors : list[Any]
        Collected errors encountered while processing the event.

    Examples
    --------
    >>> event = Event({"source": "syslog"})
    >>> event.state.current_state
    <EventStateType.RECEIVING: 'receiving'>

    >>> event_with_state = Event({"source": "api"}, state=EventState())
    >>> isinstance(event_with_state.state, EventState)
    True
    """

    __slots__: tuple[str, ...] = ("data", "state", "errors", "warnings")

    def __init__(self, data: dict[str, Any], *, state: EventState | None = None) -> None:
        self.state: EventState = EventState() if state is None else state
        self.data: dict[str, Any] = data
        self.warnings: list[Any] = []
        self.errors: list[Any] = []
        super().__init__()
