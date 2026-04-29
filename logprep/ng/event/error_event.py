"""Concrete Error Event implementation"""

import json
from datetime import datetime, timezone
from typing import Any

from logprep.ng.abc.event import Event
from logprep.ng.event.log_event import LogEvent


class ErrorEvent(Event):
    """
    ErrorEvent represents a failed event.
    """

    def __init__(self, data: dict[str, Any], parent: Event | None) -> None:
        """
        Parameters
        ----------
        log_event : LogEvent
            The event causing the error.
        reason : Exception
            The reason for the error, typically an exception.
        """
        self.parent = parent

        super().__init__(data=data)

    @staticmethod
    def from_failed_event(event: LogEvent) -> "ErrorEvent":
        return ErrorEvent(
            data={
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": str(event.errors[-1]),
                "original": event.original.decode("utf-8"),
                "event": json.dumps(event.data),
            },
            parent=event,
        )

    @staticmethod
    def from_input_failure(error: Exception, *data) -> "ErrorEvent":
        return ErrorEvent(
            data={
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": str(error),
                "event": json.dumps([*data]),
            },
            parent=None,
        )
