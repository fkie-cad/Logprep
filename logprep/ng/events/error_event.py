"""Concrete Error Event implementation"""

from datetime import datetime, timezone
from typing import Any

import msgspec

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState, EventStateType
from logprep.ng.events.log_event import LogEvent


class ErrorEvent(Event):
    """
    ErrorEvent represents a failed event.
    """

    __slots__ = ("_data", "_state", "_encoder")

    def __init__(self, log_event: LogEvent, *, state: EventState | None = None) -> None:
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
        self._encoder: msgspec.json.Encoder = msgspec.json.Encoder()
        now = datetime.now(timezone.utc).isoformat()

        if any(e.state.current_state is EventStateType.FAILED for e in log_event.extra_data):
            reason = "extra data event couldn't be delivered"
        elif log_event.state.current_state is EventStateType.FAILED:
            reason = "log event couldn't be processed or delivered"
        else:
            raise ValueError("No failed events detected")

        original = log_event.original
        try:
            event_bytes = self._encoder.encode(log_event.data)
        except (msgspec.EncodeError, TypeError) as e:
            raise e

        data: dict[str, Any] = {
            "@timestamp": now,
            "reason": reason,
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
