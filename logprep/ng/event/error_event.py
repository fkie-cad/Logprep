"""Concrete Error Event implementation"""

import json
from datetime import datetime, timezone
from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent


class ErrorEvent(Event):
    """
    ErrorEvent represents a failed event.
    """

    def __init__(
        self, log_event: LogEvent, reason: Exception, *, state: EventStateType | None = None
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
        original = log_event.original.decode("utf-8")
        event = json.dumps(log_event.data)
        data: dict[str, Any] = {
            "@timestamp": now,
            "reason": str(reason),
            "original": original,
            "event": event,
        }

        super().__init__(data=data, state=state)
