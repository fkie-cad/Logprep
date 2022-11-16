"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""
# pylint: disable=logging-fstring-interpolation
import json
from ctypes import c_bool, c_double, c_ulonglong
from logging import DEBUG, INFO, NOTSET, Handler, Logger
from multiprocessing import Lock, Process, Value, current_process
from time import time
from typing import List, TYPE_CHECKING
import warnings

import attrs
import numpy as np

from logprep._version import get_versions
from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    FatalInputError,
    SourceDisconnectedError,
    WarningInputError,
)
from logprep.abc.output import CriticalOutputError, FatalOutputError, WarningOutputError
from logprep.factory import Factory
from logprep.metrics.metric import Metric, calculate_new_average, MetricTargets
from logprep.metrics.metric_exposer import MetricExposer
from logprep.processor.base.exceptions import ProcessingWarning, ProcessingWarningCollection
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler
from logprep.util.pipeline_profiler import PipelineProfiler
from logprep.util.time_measurement import TimeMeasurement

if TYPE_CHECKING:
    from logprep.abc import Processor  # pragma: no cover


class PipelineError(BaseException):
    """Base class for Pipeline related exceptions."""


class MustProvideALogHandlerError(PipelineError):
    """Raise if no log handler was provided."""


class MultiprocessingPipelineError(PipelineError):
    """Generic multiprocessing exceptions."""


class MustProvideAnMPLogHandlerError(MultiprocessingPipelineError):
    """Raise if no multiprocessing log handler was provided."""


class Pipeline:
    """Pipeline of processors to be processed."""

    # pylint: disable=logging-not-lazy
    # Would require too much change in the tests.

    @attrs.define(kw_only=True)
    class PipelineMetrics(Metric):
        """Tracks statistics about a pipeline"""

        _prefix: str = "logprep_pipeline_"

        input: Connector.ConnectorMetrics
        """Input metrics"""
        output: Connector.ConnectorMetrics
        """Output metrics"""
        pipeline: List["Processor.ProcessorMetrics"] = attrs.Factory(list)
        """Pipeline containing the metrics of all set processors"""
        kafka_offset: int = 0
        """The current offset of the kafka input reader"""
        mean_processing_time_per_event: float = 0.0
        """Mean processing time for one event"""
        _mean_processing_time_sample_counter: int = 0

        # pylint: disable=not-an-iterable
        @property
        def number_of_processed_events(self):
            """Sum of all processed events of all processors"""
            return np.sum([processor.number_of_processed_events for processor in self.pipeline])

        @property
        def number_of_warnings(self):
            """Sum of all warnings of all processors"""
            return np.sum([processor.number_of_warnings for processor in self.pipeline])

        @property
        def number_of_errors(self):
            """Sum of all errors of all processors"""
            return np.sum([processor.number_of_errors for processor in self.pipeline])

        # pylint: enable=not-an-iterable

        def update_mean_processing_time_per_event(self, new_sample):
            """Updates the mean processing time per event"""
            new_avg, new_sample_counter = calculate_new_average(
                self.mean_processing_time_per_event,
                new_sample,
                self._mean_processing_time_sample_counter,
            )
            self.mean_processing_time_per_event = new_avg
            self._mean_processing_time_sample_counter = new_sample_counter

    def __init__(
        self,
        pipeline_index: int,
        config: dict,
        counter: "SharedCounter",
        log_handler: Handler,
        lock: Lock,
        shared_dict: dict,
        metric_targets: MetricTargets = None,
    ):
        if not isinstance(log_handler, Handler):
            raise MustProvideALogHandlerError
        self._logprep_config = config
        self._log_handler = log_handler
        self._logger = None

        self._continue_iterating = False
        self._pipeline = []
        self._input = None
        self._output = None
        self._lock = lock
        self._shared_dict = shared_dict
        self._processing_counter = counter
        self.metrics = None
        self._metric_targets = metric_targets
        self._metrics_exposer = None
        self._metric_labels = {"pipeline": f"pipeline-{pipeline_index}"}

        self._event_version_information = {
            "logprep": get_versions().get("version"),
            "configuration": self._logprep_config.get("version", "unset"),
        }

    def _setup(self):
        self._create_logger()
        self._create_connectors()
        self._create_metrics()
        self._build_pipeline()

    def _create_metrics(self):
        self._metrics_exposer = MetricExposer(
            self._logprep_config.get("metrics", {}),
            self._metric_targets,
            self._shared_dict,
            self._lock,
        )
        self.metrics = self.PipelineMetrics(
            input=self._input.metrics, output=self._output.metrics, labels=self._metric_labels
        )

    def _build_pipeline(self):
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"Building '{current_process().name}'")
        self._pipeline = []
        for entry in self._logprep_config.get("pipeline"):
            processor_name = list(entry.keys())[0]
            entry[processor_name]["metric_labels"] = self._metric_labels
            processor = Factory.create(entry, self._logger)
            self._pipeline.append(processor)
            self.metrics.pipeline.append(processor.metrics)
            if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
                self._logger.debug(f"Created '{processor}' processor ({current_process().name})")
            self._pipeline[-1].setup()
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"Finished building pipeline ({current_process().name})")

    def _create_connectors(self):
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"Creating connectors ({current_process().name})")
        input_connector_config = self._logprep_config.get("input")
        connector_name = list(input_connector_config.keys())[0]
        input_connector_config[connector_name]["metric_labels"] = self._metric_labels
        input_connector_config[connector_name].update(
            {"version_information": self._event_version_information}
        )
        self._input = Factory.create(input_connector_config, self._logger)
        output_connector_config = self._logprep_config.get("output")
        connector_name = list(output_connector_config.keys())[0]
        output_connector_config[connector_name]["metric_labels"] = self._metric_labels
        self._output = Factory.create(output_connector_config, self._logger)
        self._output.input_connector = self._input
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(
                f"Created input connector '{self._input.describe()}' " f"({current_process().name})"
            )
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(
                f"Created output connector '{self._output.describe()}' "
                f"({current_process().name})"
            )

        self._input.setup()
        self._output.setup()
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug(f"Finished creating connectors ({current_process().name})")

    def _create_logger(self):
        if self._log_handler.level == NOTSET:
            self._log_handler.level = INFO
        logger = Logger("Pipeline", level=self._log_handler.level)
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.addHandler(self._log_handler)

        self._logger = logger

    def run(self):
        """Start processing processors in the Pipeline."""
        with self._lock:
            with warnings.catch_warnings():
                warnings.simplefilter("default")
                self._setup()
        self._enable_iteration()
        try:
            if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
                self._logger.debug(f"Start iterating ({current_process().name})")
            while self._iterate():
                self._retrieve_and_process_data()
        except SourceDisconnectedError:
            self._logger.warning(
                f"Lost or failed to establish connection to {self._input.describe()}"
            )
        except FatalInputError as error:
            self._logger.error(f"Input {self._input.describe()} failed: {error}")
        except FatalOutputError as error:
            self._logger.error(f"Output {self._output.describe()} failed: {error}")

        self._shut_down()

    def _iterate(self):
        return self._continue_iterating

    def _enable_iteration(self):
        self._continue_iterating = True

    def _retrieve_and_process_data(self):
        event = {}
        try:
            self._metrics_exposer.expose(self.metrics)
            event, non_critical_error_msg = self._input.get_next(
                self._logprep_config.get("timeout")
            )
            if non_critical_error_msg:
                self._output.store_failed(non_critical_error_msg, event, None)

            try:
                self.metrics.kafka_offset = self._input.current_offset
            except AttributeError:
                pass

            if event:
                self._process_event(event)
                self._processing_counter.increment()
                self._processing_counter.print_if_ready()
                if event:
                    self._output.store(event)
                    if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
                        self._logger.debug("Stored output")
        except SourceDisconnectedError as error:
            raise error
        except WarningInputError as error:
            self._logger.warning(f"An error occurred for input {self._input.describe()}: {error}")
            self._input.metrics.number_of_warnings += 1
        except WarningOutputError as error:
            self._logger.warning(f"An error occurred for output {self._output.describe()}: {error}")
            self._output.metrics.number_of_warnings += 1
        except CriticalInputError as error:
            msg = f"A critical error occurred for input {self._input.describe()}: {error}"
            self._logger.error(msg)
            if error.raw_input:
                self._output.store_failed(msg, error.raw_input, event)
            self._input.metrics.number_of_errors += 1
        except CriticalOutputError as error:
            msg = f"A critical error occurred for output " f"{self._output.describe()}: {error}"
            self._logger.error(msg)
            if error.raw_input:
                self._output.store_failed(msg, error.raw_input, {})
            self._output.metrics.number_of_errors += 1

    @TimeMeasurement.measure_time("pipeline")
    def _process_event(self, event: dict):
        event_received = json.dumps(event, separators=(",", ":"))
        try:
            for processor in self._pipeline:
                try:
                    extra_data = processor.process(event)
                    if isinstance(extra_data, list):
                        for data in extra_data:
                            self._store_extra_data(data)
                    if isinstance(extra_data, tuple):
                        self._store_extra_data(extra_data)
                except ProcessingWarning as error:
                    self._logger.warning(
                        f"A non-fatal error occurred for processor {processor.describe()} "
                        f"when processing an event: {error}"
                    )

                    processor.metrics.number_of_warnings += 1
                except ProcessingWarningCollection as error:
                    for warning in error.processing_warnings:
                        self._logger.warning(
                            "A non-fatal error occurred for processor %s "
                            "when processing an event: %s",
                            processor.describe(),
                            warning,
                        )

                        processor.metrics.number_of_warnings += 1

                if not event:
                    if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
                        self._logger.debug(f"Event deleted by processor {processor}")
                    return
        # pylint: disable=broad-except
        except BaseException as error:
            original_error_msg = type(error).__name__
            if str(error):
                original_error_msg += f": {error}"
            msg = (
                f"A critical error occurred for processor {processor.describe()} when "
                f"processing an event, processing was aborted: ({original_error_msg})"
            )
            self._logger.error(msg)
            self._output.store_failed(msg, json.loads(event_received), event)
            event.clear()  # 'delete' the event, i.e. no regular output

            processor.metrics.number_of_errors += 1
        # pylint: enable=broad-except

    def _store_extra_data(self, extra_data: tuple):
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
            self._logger.debug("Storing extra data")
        documents = extra_data[0]
        target = extra_data[1]
        for document in documents:
            self._output.store_custom(document, target)

    def _shut_down(self):
        self._input.shut_down()
        self._output.shut_down()

        while self._pipeline:
            self._pipeline.pop().shut_down()

    def stop(self):
        """Stop processing processors in the Pipeline."""
        self._continue_iterating = False


class SharedCounter:
    """A shared counter for multi-processing pipelines."""

    CHECKING_PERIOD = 0.5

    def __init__(self):
        self._val = Value(c_ulonglong, 0)
        self._lock = Lock()
        self._timer = Value(c_double, 0)
        self._checking_timer = 0
        self._logger = None
        self._period = None

    def _init_timer(self, period: float):
        if self._period is None:
            self._period = period
        with self._lock:
            self._timer.value = time() + self._period

    def _create_logger(self, log_handler: Handler):
        if self._logger is None:
            logger = Logger("Processing Counter", level=log_handler.level)
            for handler in logger.handlers:
                logger.removeHandler(handler)
            logger.addHandler(log_handler)

            self._logger = logger

    def setup(self, print_processed_period: float, log_handler: Handler):
        """Setup shared counter for multiprocessing pipeline."""
        self._create_logger(log_handler)
        self._init_timer(print_processed_period)
        self._checking_timer = time() + self.CHECKING_PERIOD

    def increment(self):
        """Increment the counter."""
        with self._lock:
            self._val.value += 1

    def print_if_ready(self):
        """Periodically print the counter and reset it."""
        current_time = time()
        if current_time > self._checking_timer:
            self._checking_timer = current_time + self.CHECKING_PERIOD
            if self._timer.value != 0 and current_time >= self._timer.value:
                with self._lock:
                    if self._period / 60.0 < 1:
                        msg = f"Processed events per {self._period} seconds: {self._val.value}"
                    else:
                        msg = (
                            f"Processed events per {self._period / 60.0:.2f} minutes: "
                            f"{self._val.value}"
                        )
                    if self._logger:
                        self._logger.info(msg)
                    self._val.value = 0
                    self._timer.value = time() + self._period


class MultiprocessingPipeline(Process, Pipeline):
    """A thread-safe Pipeline for multi-processing."""

    processed_counter = SharedCounter()

    def __init__(
        self,
        pipeline_index: int,
        config: dict,
        log_handler: Handler,
        lock: Lock,
        shared_dict: dict,
        metric_targets: MetricTargets = None,
    ):
        if not isinstance(log_handler, MultiprocessingLogHandler):
            raise MustProvideAnMPLogHandlerError

        self._profile = config.get("profile_pipelines", False)
        print_processed_period = config.get("print_processed_period", 300)
        self.processed_counter.setup(print_processed_period, log_handler)

        Pipeline.__init__(
            self,
            pipeline_index=pipeline_index,
            config=config,
            counter=self.processed_counter,
            log_handler=log_handler,
            lock=lock,
            shared_dict=shared_dict,
            metric_targets=metric_targets,
        )

        self._continue_iterating = Value(c_bool)
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False
        Process.__init__(self)

    def run(self):
        """Start processing the Pipeline."""
        if self._profile:
            PipelineProfiler.profile_function(Pipeline.run, self)
        else:
            Pipeline.run(self)

    def _enable_iteration(self):
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True

    def _iterate(self) -> Value:
        with self._continue_iterating.get_lock():
            return self._continue_iterating.value

    def stop(self):
        """Stop processing the Pipeline."""
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False
