"""pipeline module for processing events through a series of processors."""

import logging
from collections.abc import Iterator
from functools import partial
from typing import Generator

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("Pipeline")


def _process_event(event: LogEvent | None, processors: list[Processor]) -> LogEvent:
    """process all processors for one event"""
    if event is None or not event.data:
        return None
    event.state.next_state()
    for processor in processors:
        if not event.data:
            break
        processor.process(event)
    if not event.errors:
        event.state.next_state(success=True)
    else:
        event.state.next_state(success=False)
        logger.error("event failed: %s with errors: %s", event, event.errors)
    return event


class Pipeline(Iterator):
    """Pipeline class to process events through a series of processors.
    Examples:
        >>> from logprep.ng.event.log_event import LogEvent
        >>> from logprep.ng.abc.event import Event
        >>> class MockProcessor:
        ...     def process(self, event: LogEvent) -> None:
        ...         event.data["processed"] = True
        ...
        >>>
        >>> # Create test events
        >>> events = [
        ...     LogEvent({"message": "test1"}, original=b""),
        ...     LogEvent({"message": "test2"}, original=b"")
        ... ]
        >>> processors = [MockProcessor()]
        >>>
        >>> # Create and run pipeline
        >>> pipeline = Pipeline(iter(events), processors)
        >>> processed_events = list(pipeline)
        >>> len(processed_events)
        2
        >>> processed_events[0].data["processed"]
        True
        >>> processed_events[1].data["message"]
        'test2'
    """

    def __init__(
        self,
        log_events_iter: Iterator[LogEvent],
        processors: list[Processor],
    ) -> None:
        self.processors = processors
        self.log_events_iter = log_events_iter

    def __iter__(self) -> Generator[LogEvent | None, None, None]:
        """Iterate over processed events."""

        yield from map(partial(_process_event, processors=self.processors), self.log_events_iter)

    def __next__(self):
        raise NotImplementedError("Use iteration to get processed events.")

    def shut_down(self) -> None:
        """Shutdown the pipeline gracefully."""

        for processor in self.processors:
            processor.shut_down()

        logger.info("All processors has been shut down.")
        logger.info("Pipeline has been shut down.")

    def setup(self) -> None:
        """Setup the pipeline components."""

        for processor in self.processors:
            processor.setup()

        logger.info("Pipeline has been set up.")
