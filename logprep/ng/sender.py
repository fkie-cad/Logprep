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

logger = logging.getLogger("Sender")


class LogprepExceptionGroup(ExceptionGroup):
    """Custom ExceptionGroup for Logprep exceptions to override the default
    string representation."""

    def __str__(self) -> str:
        return f"{self.message}: {self.exceptions}"


class Sender(Iterator):
    """Sender class to handle sending events to configured outputs."""

    def __init__(self, pipeline: Pipeline, outputs: list[Output], error_output: Output) -> None:
        self._events = (event for event in pipeline if event is not None and event.data)
        self._outputs = {output.name: output for output in outputs}
        self._default_output = [output for output in outputs if output.default][0]
        self._error_output = error_output
        self._all_outputs = (
            (*self._outputs.values(), self._error_output)
            if error_output is not None
            else self._outputs.values()
        )
        self.batch_size = 10
        if hasattr(self._default_output._config, "message_backlog_size"):
            self.batch_size = self._default_output._config.message_backlog_size
        self.batch: list[LogEvent] = []

    def __next__(self) -> LogEvent:
        event = next(self._events)
        if event.state == EventStateType.PROCESSED:
            self._send_processed(event)
            for output in self._outputs.values():
                output.flush()
        if self._error_output and event.state == EventStateType.FAILED:
            event = self._send_failed(event)
            self._error_output.flush()
        if isinstance(event, ErrorEvent) and event.state == EventStateType.FAILED:
            logger.error("Error during sending to error output: %s", event)
        return event

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""
        while True:
            self.batch.clear()
            self.batch += list(islice(self._events, self.batch_size))
            if not self.batch:
                break
            for event in filter(lambda x: x.state == EventStateType.PROCESSED, self.batch):
                self._send_processed(event)
            for output in self._outputs.values():
                output.flush()
            if self._error_output:
                error_events = [
                    self._send_failed(event)
                    for event in self.batch
                    if event.state == EventStateType.FAILED
                ]
                self._error_output.flush()
                failed_error_events = [
                    event for event in error_events if event.state == EventStateType.FAILED
                ]
                for error_event in failed_error_events:
                    logger.error("Error during sending to error output: %s", error_event)

            yield from self.batch

    def _send_extra_data(self, event: LogEvent) -> None:
        extra_data_events: list[ExtraDataEvent] = event.extra_data
        for extra_data_event in extra_data_events:
            for output in extra_data_event.outputs:
                for output_name, output_target in output.items():
                    if output_name in self._outputs:
                        self._outputs[output_name].store_custom(extra_data_event, output_target)
                    else:
                        raise ValueError(f"Output {output_name} not configured.")

    def _send_processed(self, event: LogEvent) -> LogEvent:
        if event.extra_data:
            self._send_extra_data(event)
        self._default_output.store(event)
        return event

    def _send_failed(self, event: LogEvent) -> ErrorEvent:
        """Send the event to the error output.
        If event can't be sent, it will be logged as an error.
        """
        error_event = self._get_error_event(event)
        self._error_output.store(error_event)
        return error_event

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
