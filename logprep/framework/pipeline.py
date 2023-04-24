"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""
# pylint: disable=logging-fstring-interpolation
import queue
import warnings
from ctypes import c_bool, c_double, c_ulonglong
from functools import cached_property
from logging import INFO, NOTSET, Handler, Logger
from multiprocessing import Lock, Process, Value, current_process
from time import time
from typing import Any, List, Tuple

import attrs
import msgspec
import numpy as np

from logprep._version import get_versions
from logprep.abc.component import Component
from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    FatalInputError,
    Input,
    SourceDisconnectedError,
    WarningInputError,
)
from logprep.abc.output import (
    CriticalOutputError,
    FatalOutputError,
    Output,
    WarningOutputError,
)
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.metrics.metric import Metric, MetricTargets, calculate_new_average
from logprep.metrics.metric_exposer import MetricExposer
from logprep.processor.base.exceptions import ProcessingCriticalError, ProcessingWarning
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler
from logprep.util.pipeline_profiler import PipelineProfiler
from logprep.util.time_measurement import TimeMeasurement


class PipelineError(BaseException):
    """Base class for Pipeline related exceptions."""


class MustProvideALogHandlerError(PipelineError):
    """Raise if no log handler was provided."""


class MustProvideAnMPLogHandlerError(BaseException):
    """Raise if no multiprocessing log handler was provided."""


class SharedCounter:
    """A shared counter for multiprocessing pipelines."""

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


def _handle_pipeline_error(func):
    def _inner(self: "Pipeline") -> Any:
        try:
            return func(self)
        except SourceDisconnectedError as error:
            self.logger.warning(str(error))
            self.stop()
        except (WarningOutputError, WarningInputError) as error:
            self.logger.warning(str(error))
        except CriticalOutputError as error:
            self.logger.error(str(error))
        except (FatalOutputError, FatalInputError) as error:
            self.logger.error(str(error))
            self.stop()
        except CriticalInputError as error:
            if raw_input := error.raw_input and self._output:  # pylint: disable=protected-access
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
    class PipelineMetrics(Metric):
        """Tracks statistics about a pipeline"""

        _prefix: str = "logprep_pipeline_"

        input: Connector.ConnectorMetrics
        """Input metrics"""
        output: List[Connector.ConnectorMetrics]
        """Output metrics"""
        pipeline: List["Processor.ProcessorMetrics"] = attrs.field(factory=list)
        """Pipeline containing the metrics of all set processors"""
        kafka_offset: int = 0
        """The current offset of the kafka input reader"""
        number_of_processed_events: int = 0
        """Number of events that this pipeline has processed"""
        mean_processing_time_per_event: float = 0.0
        """Mean processing time for one event"""
        _mean_processing_time_sample_counter: int = 0

        # pylint: disable=not-an-iterable
        @property
        def sum_of_processor_warnings(self):
            """Sum of all warnings of all processors"""
            return np.sum([processor.number_of_warnings for processor in self.pipeline])

        @property
        def sum_of_processor_errors(self):
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

    _logprep_config: dict
    """ the logprep configuration dict """

    _log_handler: Handler
    """ the handler for the logs """

    _continue_iterating: Value
    """ a flag to signal if iterating continues """

    _lock: Lock
    """ the lock for the pipeline process """

    _shared_dict: dict
    """ a shared dict for inter process communication """

    _used_server_ports: dict
    """ a shard dict for signaling used ports between pipeline processes """

    _processing_counter: SharedCounter
    """A shared counter for multi-processing pipelines."""

    pipeline_index: int
    """ the index of this pipeline """

    def __init__(
        self,
        config: dict,
        pipeline_index: int = None,
        counter: "SharedCounter" = None,
        log_handler: Handler = None,
        lock: Lock = None,
        shared_dict: dict = None,
        used_server_ports: dict = None,
        metric_targets: MetricTargets = None,
    ) -> None:
        if log_handler and not isinstance(log_handler, Handler):
            raise MustProvideALogHandlerError
        self._logprep_config = config
        self._timeout = config.get("timeout")
        self._log_handler = log_handler
        self._continue_iterating = Value(c_bool)

        self._lock = lock
        self._shared_dict = shared_dict
        self._processing_counter = counter
        self._used_server_ports = used_server_ports
        self._metric_targets = metric_targets
        self.pipeline_index = pipeline_index
        self._encoder = msgspec.msgpack.Encoder()
        self._decoder = msgspec.msgpack.Decoder()

    @cached_property
    def _process_name(self) -> str:
        return current_process().name

    @cached_property
    def _event_version_information(self) -> dict:
        return {
            "logprep": get_versions().get("version"),
            "configuration": self._logprep_config.get("version", "unset"),
        }

    @cached_property
    def _metric_labels(self) -> dict:
        return {"pipeline": f"pipeline-{self.pipeline_index}"}

    @cached_property
    def _metrics_exposer(self) -> MetricExposer:
        return MetricExposer(
            self._logprep_config.get("metrics", {}),
            self._metric_targets,
            self._shared_dict,
            self._lock,
            self.logger,
        )

    @cached_property
    def metrics(self) -> PipelineMetrics:
        """The pipeline metrics object"""
        if self._metric_targets is None:
            return None
        return self.PipelineMetrics(
            input=self._input.metrics,
            output=[self._output.get(output).metrics for output in self._output],
            labels=self._metric_labels,
        )

    @cached_property
    def _pipeline(self) -> tuple:
        self.logger.debug(f"Building '{self._process_name}'")
        pipeline = [self._create_processor(entry) for entry in self._logprep_config.get("pipeline")]
        self.logger.debug(f"Finished building pipeline ({self._process_name})")
        return pipeline

    @cached_property
    def _output(self) -> dict[str, Output]:
        output_configs = self._logprep_config.get("output")
        if not output_configs:
            return None
        output_names = list(output_configs.keys())
        outputs = {}
        for output_name in output_names:
            output_configs[output_name]["metric_labels"] = self._metric_labels
            output_config = output_configs.get(output_name)
            outputs |= {output_name: Factory.create({output_name: output_config}, self.logger)}
        return outputs

    @cached_property
    def _input(self) -> Input:
        input_connector_config = self._logprep_config.get("input")
        if input_connector_config is None:
            return None
        connector_name = list(input_connector_config.keys())[0]
        input_connector_config[connector_name]["metric_labels"] = self._metric_labels
        input_connector_config[connector_name].update(
            {"version_information": self._event_version_information}
        )
        return Factory.create(input_connector_config, self.logger)

    @cached_property
    def logger(self) -> Logger:
        """the pipeline logger"""
        if self._log_handler is None:
            return Logger("Pipeline")
        if self._log_handler.level == NOTSET:
            self._log_handler.level = INFO
        logger = Logger("Pipeline", level=self._log_handler.level)
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.addHandler(self._log_handler)

        return logger

    @_handle_pipeline_error
    def _setup(self):
        self.logger.debug(f"Creating connectors ({self._process_name})")
        for _, output in self._output.items():
            output.input_connector = self._input
        self.logger.debug(
            f"Created connectors -> input: '{self._input.describe()}',"
            f" output -> '{[output.describe() for _, output in self._output.items()]}' ({self._process_name})"
        )
        self._input.pipeline_index = self.pipeline_index
        self._input.setup()
        for _, output in self._output.items():
            output.setup()

        if hasattr(self._input, "server"):
            while self._input.server.config.port in self._used_server_ports:
                self._input.server.config.port += 1
            self._used_server_ports.update({self._input.server.config.port: self._process_name})
        self.logger.debug(f"Finished creating connectors ({self._process_name})")
        self.logger.info(f"Start building pipeline ({self._process_name})")
        _ = self._pipeline
        self.logger.info(f"Finished building pipeline ({self._process_name})")

    def _create_processor(self, entry: dict) -> "Processor":
        processor_name = list(entry.keys())[0]
        entry[processor_name]["metric_labels"] = self._metric_labels
        processor = Factory.create(entry, self.logger)
        processor.setup()
        if self.metrics:
            self.metrics.pipeline.append(processor.metrics)
        self.logger.debug(f"Created '{processor}' processor ({self._process_name})")
        return processor

    def run(self) -> None:
        """Start processing processors in the Pipeline."""
        self._enable_iteration()
        assert self._input, "Pipeline should not be run without input connector"
        assert self._output, "Pipeline should not be run without output connector"
        with self._lock:
            with warnings.catch_warnings():
                warnings.simplefilter("default")
                self._setup()
        self.logger.debug(f"Start iterating ({self._process_name})")
        if hasattr(self._input, "server"):
            with self._input.server.run_in_thread():
                while self._iterate():
                    self.process_pipeline()
        else:
            while self._iterate():
                self.process_pipeline()
        self._shut_down()

    def _iterate(self) -> bool:
        return self._continue_iterating.value

    def _enable_iteration(self) -> None:
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True

    @_handle_pipeline_error
    def process_pipeline(self) -> Tuple[dict, list]:
        """Retrieve next event, process event with full pipeline and store or return results"""
        assert self._input, "Run process_pipeline only with an valid input connector"
        self._metrics_exposer.expose(self.metrics)
        Component.run_pending_tasks()
        extra_outputs = []
        if event := self._get_event():
            extra_outputs = self.process_event(event)
        if event and self._output:
            self._store_event(event)
        return event, extra_outputs

    def _store_event(self, event: dict) -> None:
        for output_name, output in self._output.items():
            if output.default:
                output.store(event)
                self.logger.debug(f"Stored output in {output_name}")

    def _get_event(self) -> dict:
        event, non_critical_error_msg = self._input.get_next(self._timeout)
        if non_critical_error_msg and self._output:
            for _, output in self._output.items():
                if output.default:
                    output.store_failed(non_critical_error_msg, event, None)
        try:
            self.metrics.kafka_offset = self._input.current_offset
        except AttributeError:
            pass
        return event

    @TimeMeasurement.measure_time("pipeline")
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
                for _, output in self._output.items():
                    if output.default:
                        output.store_failed(str(error), self._decoder.decode(event_received), event)
            if not event:
                break
        if self._processing_counter:
            self._processing_counter.increment()
            self._processing_counter.print_if_ready()
        if self.metrics:
            self.metrics.number_of_processed_events += 1
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
        if hasattr(self._input, "server"):
            self._used_server_ports.pop(self._input.server.config.port)
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
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False


class MultiprocessingPipeline(Process, Pipeline):
    """A thread-safe Pipeline for multiprocessing."""

    processed_counter: SharedCounter = SharedCounter()

    def __init__(
        self,
        pipeline_index: int,
        config: dict,
        log_handler: Handler,
        lock: Lock,
        shared_dict: dict,
        used_server_ports: dict,
        metric_targets: MetricTargets = None,
    ) -> None:
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
            used_server_ports=used_server_ports,
            metric_targets=metric_targets,
        )

        self._continue_iterating = Value(c_bool)
        self.stop()
        Process.__init__(self)

    def run(self) -> None:
        """Start processing the Pipeline."""
        if self._profile:
            PipelineProfiler.profile_function(Pipeline.run, self)
        else:
            Pipeline.run(self)

    def _enable_iteration(self) -> None:
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True

    def _iterate(self) -> Value:
        with self._continue_iterating.get_lock():
            return self._continue_iterating.value

    def stop(self) -> None:
        """Stop processing the Pipeline."""
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False
