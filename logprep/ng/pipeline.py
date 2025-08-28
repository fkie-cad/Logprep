"""pipeline module for processing events through a series of processors."""

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import islice
from typing import Generator

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("Pipeline")


def _process_event(event: LogEvent, processors: list[Processor]) -> LogEvent:
    """process all processors for one event"""
    event.state.next_state()
    for processor in processors:
        if not event.data:
            break
        processor.process(event)
    if not event.errors:
        event.state.next_state(success=True)
    else:
        event.state.next_state(success=False)
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
        input_connector: Iterator[LogEvent],
        processors: list[Processor],
        process_count: int = 2,
    ) -> None:
        self._processors = processors
        self._process_count = process_count
        self._events = (event for event in input_connector if event is not None and event.data)

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""
        events = self._events
        process_count = self._process_count
        processors = self._processors
        while True:
            batch = list(islice(events, process_count))
            if not batch:
                break
            with ThreadPoolExecutor(max_workers=process_count) as executor:
                yield from executor.map(partial(_process_event, processors=processors), batch)

    def __next__(self):
        raise NotImplementedError("Use iteration to get processed events.")

    def shut_down(self) -> None:
        """Shutdown the pipeline gracefully."""
        for processor in self._processors:
            processor.shut_down()
        logger.debug("Pipeline has been shut down.")

    def setup(self) -> None:
        """Setup the pipeline components."""
        for processor in self._processors:
            processor.setup()
        logger.debug("Pipeline has been set up.")
