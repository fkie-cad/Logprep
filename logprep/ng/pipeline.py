"""pipeline module for processing events through a series of processors."""

from collections.abc import Iterator
from itertools import islice
from typing import Generator

from logprep.ng.abc.event import Event
from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent


class Pipeline:
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
        >>> processed_events = list(pipeline.process_pipeline())
        >>> len(processed_events)
        2
        >>> processed_events[0].data["processed"]
        True
        >>> processed_events[1].data["message"]
        'test2'
    """

    def __init__(self, input_connector: Iterator[Event], processors: list[Processor]) -> None:
        self._input = input_connector
        self._processors = processors

    def process_pipeline(self) -> Generator[LogEvent, None, None]:
        """processes the Pipeline"""
        while True:
            events = (event for event in self._input if event is not None and event.data)
            batch = list(islice(events, 10))
            if not batch:
                break
            yield from map(self.process_event, batch)

    def process_event(self, event: LogEvent) -> LogEvent:
        """process all processors for one event"""
        event.state.next_state()
        for processor in self._processors:
            if not event.data:
                break
            processor.process(event)
        if not event.errors:
            event.state.next_state(success=True)
        else:
            event.state.next_state(success=False)
        return event
