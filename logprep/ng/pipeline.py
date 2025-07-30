from collections.abc import Iterator
from itertools import islice
from typing import Generator

from logprep.ng.abc.event import Event
from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent


class Pipeline:

    def __init__(self, input_connector: Iterator[Event], processors: list[Processor]) -> None:
        self._input = input_connector
        self._processors = processors

    def process_pipeline(self) -> Generator[LogEvent, None, None]:
        """processes the Pipeline"""
        while True:
            batch = list(islice(self._input, 10))
            if not batch:
                break
            yield from map(self.process_event, batch)

    def process_event(self, event: LogEvent) -> LogEvent:
        """process all processors for one event"""
        event.state.next_state()
        for processor in self._processors:
            processor.process(event)
        if not event.errors:
            event.state.next_state(success=True)
        else:
            event.state.next_state(success=False)

        return event
