"""pipeline module for processing events through a series of processors."""

from collections.abc import Iterator
from itertools import islice
from typing import Generator

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent


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
        process_count: int = 10,
    ) -> None:
        self._input = input_connector
        self._processors = processors
        self._process_count = process_count

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""
        while True:
            events = (event for event in self._input if event is not None and event.data)
            batch = list(islice(events, self._process_count))
            if not batch:
                break
            yield from map(self._process_event, batch)

    def __next__(self):
        """
        Return the next processed event or None if no valid event is found.

        This method intentionally deviates from the standard Python iterator protocol.
        Normally, __next__() must raise StopIteration to signal that there are no more
        items. In this Pipeline, __next__() instead returns None when no valid event
        is available. This design allows callers to check for "no event" without
        handling StopIteration explicitly, but means the method is not strictly
        iterator-compliant by design.
        """
        try:
            while (next_event := next(self._input)) is None or not next_event.data:
                continue
        except StopIteration:
            return None
        return self._process_event(next_event)

    def _process_event(self, event: LogEvent) -> LogEvent:
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
