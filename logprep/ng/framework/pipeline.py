import itertools
from functools import cached_property
from importlib.metadata import version

import attrs

from logprep.abc.processor import ProcessorResult
from logprep.factory import Factory
from logprep.ng.abc.event import Event
from logprep.ng.abc.input import Input
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.processor.base.exceptions import ProcessingError, ProcessingWarning
from logprep.util.configuration import Configuration


@attrs.define(kw_only=True)
class PipelineResult:
    """Result object to be returned after processing the event.
    It contains all results of each processor of the pipeline.

    Parameters
    ----------

    event : dict
        The event that was processed
    pipeline : List[Processor]
        The pipeline that processed the event

    Returns
    -------
    PipelineResult
        The result object
    """

    __match_args__ = ("event", "errors")

    results: list[ProcessorResult] = attrs.field(
        validator=[
            attrs.validators.instance_of(list),
            attrs.validators.deep_iterable(
                member_validator=attrs.validators.instance_of(ProcessorResult)
            ),
        ],
        init=False,
    )
    """List of ProcessorResults. Is populated in __attrs_post_init__"""
    event: Event = attrs.field(validator=attrs.validators.instance_of(Event))
    """The event that was processed"""

    pipeline: list[Processor] = attrs.field(
        validator=[
            attrs.validators.deep_iterable(
                member_validator=attrs.validators.instance_of(Processor),
                iterable_validator=attrs.validators.instance_of(list),
            ),
            attrs.validators.min_len(1),
        ]
    )
    """The pipeline that processed the event"""

    @cached_property
    def errors(self) -> list[ProcessingError]:
        """Return all processing errors."""
        return list(itertools.chain(*[result.errors for result in self]))

    @cached_property
    def warnings(self) -> list[ProcessingWarning]:
        """Return all processing warnings."""
        return list(itertools.chain(*[result.warnings for result in self]))

    @cached_property
    def data(self) -> list[tuple[dict, dict]]:
        """Return all extra data."""
        return list(itertools.chain(*[result.data for result in self]))

    def __attrs_post_init__(self):
        self.results = [processor.process(self.event) for processor in self.pipeline if self.event]

    def __iter__(self):
        return iter(self.results)


class Pipeline:
    """Pipeline of processors to be processed."""

    def __iter__(self):
        return self

    def __next__(self):
        event = self._input.get_next(self._timeout)
        if not event:
            raise StopIteration

        return self.process_event(event)

    _logprep_config: Configuration
    """ the logprep configuration dict """

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

    def run(self):
        """Start processing processors in the Pipeline."""
        self.process_pipeline()

    def process_pipeline(self):
        """Retrieve next event, process event with full pipeline and store or return results"""
        event = self._input.get_next(self._timeout)
        if not event:
            return
        event.state.next_state()
        result = None
        if self._pipeline:
            self.process_events(event)

        if event.state.current_state is EventStateType.FAILED:
            event.state.next_state(success=False)
        else:
            event.state.next_state(success=True)
        return result

    def process_events(self, events: list[Event]) -> list[PipelineResult]:
        """Maps a batch of events to the process_events"""
        return list(map(self.process_event, events))

    def process_event(self, event):
        """process all processors for one event"""
        event.state.next_state()
        result = PipelineResult(
            event=event,
            pipeline=self._pipeline,
        )
        for extra_event in result:
            event.extra_data.append(extra_event)
        return result

    def _create_processor(self, entry: dict) -> "Processor":
        processor = Factory.create(entry)
        processor.setup()
        return processor

    def _setup(self):
        self._input.setup()
        _ = self._pipeline
