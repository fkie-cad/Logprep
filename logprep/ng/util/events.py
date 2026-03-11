from collections import defaultdict
from collections.abc import Sequence
from typing import TypeVar

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventStateType

E_co = TypeVar("E_co", bound=Event, covariant=True)


def partition_by_state(events: Sequence[E_co]) -> dict[EventStateType, list[E_co]]:
    result = defaultdict(list)

    for event in events:
        result[event.state.current_state].append(event)

    return result
