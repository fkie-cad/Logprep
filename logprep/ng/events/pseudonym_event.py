"""Concrete Pseudonym Event implementation"""

from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState


class PseudonymEvent(Event):
    """Concrete Pseudonym event class."""

