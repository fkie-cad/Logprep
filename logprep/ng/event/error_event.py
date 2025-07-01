"""Concrete Error Event implementation"""

from datetime import datetime, timezone
from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState
from logprep.ng.event.log_event import LogEvent


class ErrorEvent(Event):
    """
    ErrorEvent represents a failed event.
    """

    def __init__(
        self, log_event: LogEvent, reason: Exception, *, state: EventState | None = None
    ) -> None:
        """
        Parameters
        ----------
        log_event : LogEvent
            The event causing the error.
        reason : Exception
            The reason for the error, typically an exception.
        state : EventState, optional
            An optional initial EventState. Defaults to a new EventState() if not provided.
        """
        now = datetime.now(timezone.utc).isoformat()
        original = log_event.original
        event_bytes = str(log_event.data).encode("utf-8")
        data: dict[str, Any] = {
            "@timestamp": now,
            "reason": str(reason),
            "original": original,
            "event": event_bytes,
        }

        super().__init__(data=data, state=state)
