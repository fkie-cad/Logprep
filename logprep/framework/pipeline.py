"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""

import copy
import logging
import logging.handlers
import multiprocessing

# pylint: disable=logging-fstring-interpolation
import queue
import warnings
from ctypes import c_bool
from functools import cached_property, partial
from importlib.metadata import version
from multiprocessing import Lock, Value, current_process
from typing import Any, List, Tuple

import attrs
import msgspec

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
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.metrics.metrics import HistogramMetric, Metric
from logprep.processor.base.exceptions import ProcessingCriticalError, ProcessingWarning
from logprep.util.configuration import Configuration
from logprep.util.pipeline_profiler import PipelineProfiler


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

    _log_queue: multiprocessing.Queue
    """ the handler for the logs """

    _continue_iterating: Value
    """ a flag to signal if iterating continues """

    _lock: Lock
    """ the lock for the pipeline process """

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
    def _pipeline(self) -> tuple:
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
            outputs |= {output_name: Factory.create({output_name: output_config}, self.logger)}
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
        return Factory.create(input_connector_config, self.logger)

    def __init__(
        self,
        config: Configuration,
        pipeline_index: int = None,
        log_queue: multiprocessing.Queue = None,
        lock: Lock = None,
    ) -> None:
        self._log_queue = log_queue
        self.logger = logging.getLogger(f"Logprep Pipeline {pipeline_index}")
        self.logger.addHandler(logging.handlers.QueueHandler(log_queue))
        self._logprep_config = config
        self._timeout = config.timeout
        self._continue_iterating = Value(c_bool)

        self._lock = lock
        self.pipeline_index = pipeline_index
        self._encoder = msgspec.msgpack.Encoder()
        self._decoder = msgspec.msgpack.Decoder()
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
        processor = Factory.create(entry, self.logger)
        processor.setup()
        self.logger.debug(f"Created '{processor}' processor")
        return processor

    def run(self) -> None:
        """Start processing processors in the Pipeline."""
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True
        assert self._input, "Pipeline should not be run without input connector"
        assert self._output, "Pipeline should not be run without output connector"
        with self._lock:
            with warnings.catch_warnings():
                warnings.simplefilter("default")
                self._setup()
        self.logger.debug("Start iterating")
        while self._continue_iterating.value:
            self.process_pipeline()
        self._shut_down()

    @_handle_pipeline_error
    def process_pipeline(self) -> Tuple[dict, list]:
        """Retrieve next event, process event with full pipeline and store or return results"""
        Component.run_pending_tasks()
        extra_outputs = []
        event = None
        try:
            event = self._get_event()
        except CriticalInputParsingError as error:
            input_data = error.raw_input
            if isinstance(input_data, bytes):
                input_data = input_data.decode("utf8")
            error_event = self._encoder.encode({"invalid_json": input_data})
            self._store_failed_event(error, "", error_event)
            self.logger.error(f"{error}, event was written to error output")
        if event:
            extra_outputs = self.process_event(event)
        if event and self._output:
            self._store_event(event)
        return event, extra_outputs

    def _store_event(self, event: dict) -> None:
        for output_name, output in self._output.items():
            if output.default:
                output.store(event)
                self.logger.debug(f"Stored output in {output_name}")

    def _store_failed_event(self, error, event, event_received):
        for _, output in self._output.items():
            if output.default:
                output.store_failed(str(error), self._decoder.decode(event_received), event)

    def _get_event(self) -> dict:
        event, non_critical_error_msg = self._input.get_next(self._timeout)
        if non_critical_error_msg and self._output:
            for _, output in self._output.items():
                if output.default:
                    output.store_failed(non_critical_error_msg, event, None)
        return event

    @Metric.measure_time()
    def process_event(self, event: dict):
        """process all processors for one event"""

        event_received = self._encoder.encode(event)
        extra_outputs = []
        for processor in self._pipeline:
            try:
                if extra_data := processor.process(event):
                    if self._output:
                        self._store_extra_data(extra_data)
                    extra_outputs.append(extra_data)
            except ProcessingWarning as error:
                self.logger.warning(str(error))
            except ProcessingCriticalError as error:
                self.logger.error(str(error))
                if self._output:
                    self._store_failed_event(error, copy.deepcopy(event), event_received)
                    event.clear()
            if not event:
                break
        return extra_outputs

    def _store_extra_data(self, extra_data: List[tuple]) -> None:
        self.logger.debug("Storing extra data")
        if isinstance(extra_data, tuple):
            documents, outputs = extra_data
            for document in documents:
                for output in outputs:
                    for output_name, topic in output.items():
                        self._output[output_name].store_custom(document, topic)
            return
        list(map(self._store_extra_data, extra_data))

    def _shut_down(self) -> None:
        self._input.shut_down()
        self._drain_input_queues()
        for _, output in self._output.items():
            output.shut_down()
        for processor in self._pipeline:
            processor.shut_down()

    def _drain_input_queues(self) -> None:
        if not hasattr(self._input, "messages"):
            return
        if isinstance(self._input.messages, queue.Queue):
            while self._input.messages.qsize():
                self.process_pipeline()

    def stop(self) -> None:
        """Stop processing processors in the Pipeline."""
        self.logger.debug(f"Stopping pipeline ({self._process_name})")
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False
