"""sender module"""

import logging
from collections.abc import Iterator
from itertools import islice
from typing import Generator

from logprep.ng.abc.event import ExtraDataEvent
from logprep.ng.abc.output import Output
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline
from logprep.util.decorators import timeout
from logprep.util.defaults import ERROR_OUTPUT_TIMEOUT

logger = logging.getLogger("Sender")


class LogprepExceptionGroup(ExceptionGroup):
    """Custom ExceptionGroup for Logprep exceptions to override the default
    string representation."""

    def __str__(self) -> str:
        return f"{self.message}: {self.exceptions}"


class Sender(Iterator):
    """Sender class to handle sending events to configured outputs."""

    def __init__(self, pipeline: Pipeline, outputs: list[Output], error_output: Output) -> None:
        self._pipeline = pipeline
        self._outputs = {output.name: output for output in outputs}
        self._default_output = [output for output in outputs if output.default][0]
        self._error_output = error_output

    def __next__(self) -> LogEvent:
        event = next(self._pipeline)
        return self._send(event)

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""
        while True:
            events = (event for event in self._pipeline if event is not None and event.data)
            batch = list(islice(events, self._pipeline._process_count))
            if not batch:
                break
            yield from map(self._send, batch)

    def _send_extra_data(self, event: LogEvent) -> None:
        extra_data_events: list[ExtraDataEvent] = event.extra_data
        for extra_data_event in extra_data_events:
            for output in extra_data_event.outputs:
                for output_name, output_target in output.items():
                    if output_name in self._outputs:
                        self._outputs[output_name].store_custom(extra_data_event, output_target)
                    else:
                        raise ValueError(f"Output {output_name} not configured.")

    def _send(self, event: LogEvent) -> LogEvent:
        if event.extra_data:
            self._send_extra_data(event)
        if event.state.current_state == EventStateType.PROCESSED:
            self._default_output.store(event)
        elif event.state.current_state == EventStateType.FAILED and self._error_output:
            self._send_to_error_output(event)
        return event

    def _send_to_error_output(self, event: LogEvent) -> None:
        """Send the event to the error output.
        If event can't be sent, it will be logged as an error.
        """
        error_event = self._get_error_event(event)
        try:
            self._error_output.store(error_event)
            self._wait_for_error_output_delivery(error_event)
        except Exception as error:  # pylint: disable=broad-except
            error_event.data["reason"] = str(error)
            logger.error("Can't deliver to error output: %s", error_event)

    @timeout(seconds=ERROR_OUTPUT_TIMEOUT, error_message="Error output delivery timed out.")
    def _wait_for_error_output_delivery(self, error_event: ErrorEvent) -> None:
        while not error_event.state in (EventStateType.DELIVERED, EventStateType.FAILED):
            pass

    def _get_error_event(self, event: LogEvent) -> ErrorEvent:
        """returns an ErrorEvent instance based on the provided LogEvent.
        The state of the ErrorEvent is set to PROCESSED
        """
        reason = (
            LogprepExceptionGroup("Error during processing", event.errors)
            if event.errors
            else Exception("Unknown error")
        )
        return ErrorEvent(log_event=event, reason=reason, state=EventStateType.PROCESSED)
