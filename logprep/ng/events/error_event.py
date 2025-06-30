"""Concrete Error Event implementation"""

from datetime import datetime, timezone
from typing import Any

import msgspec

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState
from logprep.ng.events.log_event import LogEvent


class ErrorEvent(Event):
    """
    ErrorEvent represents a failed event.
    """

    __slots__ = ("_data", "_state", "_encoder")

    def __init__(
        self, log_event: LogEvent, reason: Exception, *, state: EventState | None = None
    ) -> None:
        """
        Parameters
        ----------
        log_event : LogEvent
            The event that could not be delivered or processed.

        Attributes
        ----------
        data : dict
            A dictionary holding the error information:
            {
                "@timestamp": str (ISO-8601),
                "reason": str,
                "original": bytes,
                "event": bytes
            }
        """
        self._state: EventState = EventState() if state is None else state
        now = datetime.now(timezone.utc).isoformat()
        self._encoder: msgspec.json.Encoder = msgspec.json.Encoder()
        original = log_event.original

        try:
            event_bytes = self._encoder.encode(log_event.data)
        except (msgspec.EncodeError, TypeError) as e:
            raise e

        data: dict[str, Any] = {
            "@timestamp": now,
            "reason": str(reason),
            "original": original,
            "event": event_bytes,
        }

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
