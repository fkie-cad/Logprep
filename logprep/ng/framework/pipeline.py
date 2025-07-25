"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""

from functools import cached_property
from importlib.metadata import version
from itertools import islice
from typing import Self

from logprep.factory import Factory
from logprep.ng.abc.event import Event
from logprep.ng.abc.input import Input
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.util.configuration import Configuration


class Pipeline:
    """Pipeline of processors to be processed."""

    process_count: int = 5

    def __init__(
        self,
        config: Configuration,
    ) -> None:
        self._logprep_config = config
        self._timeout = config.timeout

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Event:
        return next(self._input)

    @cached_property
    def _pipeline(self) -> list[Processor]:
        pipeline = [self._create_processor(entry) for entry in self._logprep_config.pipeline]

        if len(pipeline) == 0:
            raise ValueError("Length of 'pipeline' must be >= 1")
        if not all(isinstance(p, Processor) for p in pipeline):
            raise TypeError("All elements in pipeline must be instances of Processor.")

        return pipeline

    @cached_property
    def _event_version_information(self) -> dict:
        return {
            "logprep": version("logprep"),
            "configuration": self._logprep_config.version,
        }

    @cached_property
    def _input(self) -> Input | None:
        input_connector_config = self._logprep_config.input
        if not input_connector_config:
            return None
        connector_name = list(input_connector_config.keys())[0]
        input_connector_config[connector_name].update(
            {"version_information": self._event_version_information}
        )
        return Factory.create(input_connector_config)

    def _create_processor(self, entry: dict) -> "Processor":
        processor = Factory.create(entry)
        processor.setup()
        return processor

    def _setup(self) -> None:
        self._input.setup()
        _ = self._pipeline

    def process_pipeline(self):
        """processes the Pipeline"""
        while True:
            batch = list(islice(self._input, self.process_count))
            if not batch:
                break

            for event in batch:
                event.state.next_state()

            results = map(self.process_event, batch)
            yield from results

    def process_event(self, event: LogEvent) -> LogEvent:
        """process all processors for one event"""
        event.state.next_state()
        for processor in self._pipeline:
            processor.process(event)

        for extra_event in event.extra_data:
            extra_event.state.current_state = EventStateType.PROCESSED  # type: ignore

        self._input.backlog.register(event.extra_data)

        event.state.next_state(success=not any(event.errors))

        return event
