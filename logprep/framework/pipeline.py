"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""

import copy
import itertools
import logging
import logging.handlers
import multiprocessing

# pylint: disable=logging-fstring-interpolation
import multiprocessing.queues
import warnings
from ctypes import c_bool
from functools import cached_property, partial
from importlib.metadata import version
from multiprocessing import Value, current_process
from typing import Any, Generator, List, Tuple

import attrs

from logprep.abc.component import Component
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    InputWarning,
    SourceDisconnectedWarning,
)
from logprep.abc.output import (
    CriticalOutputError,
    FatalOutputError,
    Output,
    OutputWarning,
)
from logprep.abc.processor import Processor, ProcessorResult
from logprep.factory import Factory
from logprep.metrics.metrics import HistogramMetric, Metric
from logprep.processor.base.exceptions import ProcessingError, ProcessingWarning
from logprep.util.configuration import Configuration
from logprep.util.pipeline_profiler import PipelineProfiler


@attrs.define(kw_only=True)
class PipelineResult:
    """Result object to be returned after processing the event.
    It contains all results of each processor of the pipeline."""

    results: List[ProcessorResult] = attrs.field(
        validator=[
            attrs.validators.instance_of((list, Generator)),
            attrs.validators.deep_iterable(
                member_validator=attrs.validators.instance_of(ProcessorResult)
            ),
        ]
    )
    """List of ProcessorResults"""
    event: dict = attrs.field(validator=attrs.validators.instance_of(dict))
    """The event that was processed"""
    event_received: dict = attrs.field(
        validator=attrs.validators.instance_of(dict), converter=copy.deepcopy
    )
    """The event that was received"""
    pipeline: list[Processor]
    """The pipeline that processed the event"""

    @cached_property
    def errors(self) -> List[ProcessingError]:
        """Return all processing errors."""
        return list(itertools.chain(*[result.errors for result in self]))

    @cached_property
    def warnings(self) -> List[ProcessingWarning]:
        """Return all processing warnings."""
        return list(itertools.chain(*[result.warnings for result in self]))

    @cached_property
    def data(self) -> List[Tuple[dict, dict]]:
        """Return all extra data."""
        return list(itertools.chain(*[result.data for result in self]))

    def __attrs_post_init__(self):
        self.results = list(
            (processor.process(self.event) for processor in self.pipeline if self.event)
        )

    def __iter__(self):
        return iter(self.results)


def _handle_pipeline_error(func):
    def _inner(self: "Pipeline") -> Any:
        try:
            return func(self)
        except SourceDisconnectedWarning as error:
            self.logger.warning(str(error))
            self.stop()
        except (OutputWarning, InputWarning) as error:
            self.logger.warning(str(error))
        except CriticalOutputError as error:
            self.logger.error(str(error))
        except (FatalOutputError, FatalInputError) as error:
            self.logger.error(str(error))
            self.stop()
        except CriticalInputError as error:
            if (raw_input := error.raw_input) and self._output:  # pylint: disable=protected-access
                for _, output in self._output.items():  # pylint: disable=protected-access
                    if output.default:
                        output.store_failed(str(self), raw_input, {})
            self.logger.error(str(error))
        return None

    return _inner


class Pipeline:
    """Pipeline of processors to be processed."""

    # pylint: disable=logging-not-lazy
    # Would require too much change in the tests.

    @attrs.define(kw_only=True)
    class Metrics(Component.Metrics):
        """Tracks statistics about a pipeline"""

        processing_time_per_event: HistogramMetric = attrs.field(
            factory=lambda: HistogramMetric(
                description="Time in seconds that it took to process an event",
                name="processing_time_per_event",
            )
        )
        """Time in seconds that it took to process an event"""

    _logprep_config: Configuration
    """ the logprep configuration dict """

    _continue_iterating: Value
    """ a flag to signal if iterating continues """

    pipeline_index: int
    """ the index of this pipeline """

    @cached_property
    def metrics(self):
        """create and return metrics object"""
        return self.Metrics(labels=self.metric_labels)

    @cached_property
    def _process_name(self) -> str:
        return current_process().name

    @cached_property
    def _event_version_information(self) -> dict:
        return {
            "logprep": version("logprep"),
            "configuration": self._logprep_config.version,
        }

    @property
    def metric_labels(self) -> dict:
        """Return the metric labels for this component."""
        return {
            "component": "pipeline",
            "name": self._process_name,
            "type": "",
            "description": "",
        }

    @cached_property
    def _pipeline(self) -> list[Processor]:
        self.logger.debug(f"Building '{self._process_name}'")
        pipeline = [self._create_processor(entry) for entry in self._logprep_config.pipeline]
        self.logger.debug("Finished building pipeline")
        return pipeline

    @cached_property
    def _output(self) -> dict[str, Output]:
        output_configs = self._logprep_config.output
        if not output_configs:
            return None
        output_names = list(output_configs.keys())
        outputs = {}
        for output_name in output_names:
            output_config = output_configs.get(output_name)
            outputs |= {output_name: Factory.create({output_name: output_config})}
        return outputs

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

    def __init__(self, config: Configuration, pipeline_index: int = None) -> None:
        self.logger = logging.getLogger("Pipeline")
        self.logger.name = f"Pipeline{pipeline_index}"
        self._logprep_config = config
        self._timeout = config.timeout
        self._continue_iterating = Value(c_bool)
        self.pipeline_index = pipeline_index
        if self._logprep_config.profile_pipelines:
            self.run = partial(PipelineProfiler.profile_function, self.run)

    @_handle_pipeline_error
    def _setup(self):
        self.logger.debug("Creating connectors")
        for _, output in self._output.items():
            output.input_connector = self._input
            if output.default:
                self._input.output_connector = output
        self.logger.debug(
            f"Created connectors -> input: '{self._input.describe()}',"
            f" output -> '{[output.describe() for _, output in self._output.items()]}'"
        )
        self._input.pipeline_index = self.pipeline_index
        self._input.setup()
        for _, output in self._output.items():
            output.setup()

        self.logger.debug("Finished creating connectors")
        self.logger.info("Start building pipeline")
        _ = self._pipeline
        self.logger.info("Finished building pipeline")

    def _create_processor(self, entry: dict) -> "Processor":
        processor = Factory.create(entry)
        processor.setup()
        self.logger.debug(f"Created '{processor}' processor")
        return processor

    def run(self) -> None:  # pylint: disable=method-hidden
        """Start processing processors in the Pipeline."""
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True
        assert self._input, "Pipeline should not be run without input connector"
        assert self._output, "Pipeline should not be run without output connector"
        with warnings.catch_warnings():
            warnings.simplefilter("default")
            self._setup()
        self.logger.debug("Start iterating")
        while self._continue_iterating.value:
            self.process_pipeline()
        self._shut_down()

    @_handle_pipeline_error
    def process_pipeline(self) -> PipelineResult:
        """Retrieve next event, process event with full pipeline and store or return results"""
        Component.run_pending_tasks()

        event = self._get_event()
        if not event:
            return None, None
        result: PipelineResult = self.process_event(event)
        if result.warnings:
            self.logger.warning(",".join((str(warning) for warning in result.warnings)))
        if result.errors:
            self.logger.error(",".join((str(error) for error in result.errors)))
            self._store_failed_event(result.errors, result.event_received, event)
            return
        if self._output:
            result_data = [res.data for res in result if res.data]
            if result_data:
                self._store_extra_data(itertools.chain(*result_data))
            if event:
                self._store_event(event)
        return result

    def _store_event(self, event: dict) -> None:
        for output_name, output in self._output.items():
            if output.default:
                output.store(event)
                self.logger.debug(f"Stored output in {output_name}")

    def _store_failed_event(self, error, event_received, event):
        for _, output in self._output.items():
            if output.default:
                output.store_failed(str(error), event_received, event)

    def _get_event(self) -> dict:
        try:
            event, non_critical_error_msg = self._input.get_next(self._timeout)
            if non_critical_error_msg and self._output:
                self._store_failed_event(non_critical_error_msg, event, None)
            return event
        except CriticalInputParsingError as error:
            input_data = error.raw_input
            if isinstance(input_data, bytes):
                input_data = input_data.decode("utf8")
            self._store_failed_event(error, {"invalid_json": input_data}, "")

    @Metric.measure_time()
    def process_event(self, event: dict):
        """process all processors for one event"""
        result = PipelineResult(
            results=[],
            event_received=event,
            event=event,
            pipeline=self._pipeline,
        )
        return result

    def _store_extra_data(self, result_data: List | itertools.chain) -> None:
        self.logger.debug("Storing extra data")
        for document, outputs in result_data:
            for output in outputs:
                for output_name, target in output.items():
                    self._output[output_name].store_custom(document, target)

    def _shut_down(self) -> None:
        try:
            self._input.shut_down()
            self._drain_input_queues()
            for _, output in self._output.items():
                output.shut_down()
            for processor in self._pipeline:
                processor.shut_down()
        except Exception as error:  # pylint: disable=broad-except
            self.logger.error(f"Couldn't gracefully shut down pipeline due to: {error}")

    def _drain_input_queues(self) -> None:
        if not hasattr(self._input, "messages"):
            return
        if isinstance(self._input.messages, multiprocessing.queues.Queue):
            while self._input.messages.qsize():
                self.process_pipeline()

    def stop(self) -> None:
        """Stop processing processors in the Pipeline."""
        self.logger.debug(f"Stopping pipeline ({self._process_name})")
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False
