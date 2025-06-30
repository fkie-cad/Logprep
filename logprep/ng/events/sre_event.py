"""Concrete Sre Event implementation"""

from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState


class SreEvent(Event):
    """Concrete Sre event class."""

        """
        self._state = value
