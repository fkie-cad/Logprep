"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""

from functools import cached_property
from importlib.metadata import version
from itertools import islice

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.util.configuration import Configuration


class Pipeline:
    """Pipeline of processors to be processed."""

    _logprep_config: Configuration
    """ the logprep configuration dict """

    process_count = 5

    @cached_property
    def _pipeline(self) -> list[Processor]:
        pipeline = [self._create_processor(entry) for entry in self._logprep_config.pipeline]
        return pipeline

    @cached_property
    def _event_version_information(self) -> dict:
        return {
            "logprep": version("logprep"),
            "configuration": self._logprep_config.version,
        }

    @cached_property
    def _input(self) -> Input:
        input_connector_config = self._logprep_config.input
        if not input_connector_config:
            return None
        connector_name = list(input_connector_config.keys())[0]
        input_connector_config[connector_name].update(
            {"version_information": self._event_version_information}
        )
        return Factory.create(input_connector_config)

    def __init__(
        self,
        config: Configuration,
    ) -> None:
        self._logprep_config = config
        self._timeout = config.timeout

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._input)

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

    def process_event(self, event):
        """process all processors for one event"""
        event.state.next_state()
        for processor in self._pipeline:
            processor.process(event)
        for extra_event in event.extra_data:
            extra_event.state.current_state = EventStateType.PROCESSED
            self._input.backlog.append(extra_event)
        if any(event.errors):
            event.state.next_state(success=False)
        else:
            event.state.next_state(success=True)

        return event

    def _create_processor(self, entry: dict) -> "Processor":
        processor = Factory.create(entry)
        processor.setup()
        return processor

    def _setup(self):
        self._input.setup()
        _ = self._pipeline
