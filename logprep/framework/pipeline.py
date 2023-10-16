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
from ctypes import c_bool, c_ulonglong
from functools import cached_property
from multiprocessing import Lock, Process, Value, current_process
from typing import Any, List, Tuple

import attrs
import msgspec
from schedule import Scheduler

from logprep._version import get_versions
from logprep.abc.component import Component
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
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
from logprep.metrics.metrics import HistogramMetric
from logprep.processor.base.exceptions import ProcessingCriticalError, ProcessingWarning
from logprep.util.pipeline_profiler import PipelineProfiler
from logprep.util.prometheus_exporter import PrometheusStatsExporter
from logprep.util.time_measurement import TimeMeasurement


class SharedCounter:
    """A shared counter for multiprocessing pipelines."""

    def __init__(self):
        self._val = Value(c_ulonglong, 0)
        self._printed = Value(c_bool, False)
        self._lock = None
        self._period = None
        self.scheduler = Scheduler()
        self._logger = logging.getLogger("Logprep SharedCounter")

    def _init_timer(self, period: float):
        if self._period is None:
            self._period = period
        jobs = map(lambda job: job.job_func.func, self.scheduler.jobs)
        if self.print_value not in jobs and self.reset_printed not in jobs:
            self.scheduler.every(int(self._period)).seconds.do(self.print_value)
            self.scheduler.every(int(self._period + 1)).seconds.do(self.reset_printed)

    def setup(self, print_processed_period: float, lock: Lock):
        """Setup shared counter for multiprocessing pipeline."""
        self._init_timer(print_processed_period)
        self._lock = lock

    def increment(self):
        """Increment the counter."""
        with self._lock:
            self._val.value += 1

    def reset_printed(self):
        """Reset the printed flag after the configured period + 1"""
        with self._lock:
            self._printed.value = False

    def print_value(self):
        """Print the number of processed event in the last interval"""
        with self._lock:
            if not self._printed.value:
                period_human_form = f"{self._period} seconds"
                if self._period / 60.0 > 1:
                    period_human_form = f"{self._period / 60.0:.2f} minutes"
                self._logger.info(
                    f"Processed events per {period_human_form}: " f"{self._val.value}"
                )
                self._val.value = 0
                self._printed.value = True


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
    class Metrics(Component.Metrics):
        """Tracks statistics about a pipeline"""

        processing_time_per_event: HistogramMetric = attrs.field(
            factory=lambda: HistogramMetric(
                description="Time in seconds that it took to process an event",
                name="processing_time_per_event",
            )
        )
        """Time in seconds that it took to process an event"""

    _logprep_config: dict
    """ the logprep configuration dict """

    _log_queue: multiprocessing.Queue
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
        log_queue: multiprocessing.Queue = None,
        lock: Lock = None,
        shared_dict: dict = None,
        used_server_ports: dict = None,
        prometheus_exporter: PrometheusStatsExporter = None,
    ) -> None:
        self._log_queue = log_queue
        self.logger = logging.getLogger(f"Logprep Pipeline {pipeline_index}")
        self.logger.addHandler(logging.handlers.QueueHandler(log_queue))
        self._logprep_config = config
        self._timeout = config.get("timeout")
        self._continue_iterating = Value(c_bool)

        self._lock = lock
        self._shared_dict = shared_dict
        self._processing_counter = counter
        if self._processing_counter:
            print_processed_period = self._logprep_config.get("print_processed_period", 300)
            self._processing_counter.setup(print_processed_period, lock)
        self._used_server_ports = used_server_ports
        self._prometheus_exporter = prometheus_exporter
        self.pipeline_index = pipeline_index
        self._encoder = msgspec.msgpack.Encoder()
        self._decoder = msgspec.msgpack.Decoder()
        self.metrics = self.Metrics(
            labels=self.metric_labels,
        )

    @cached_property
    def _process_name(self) -> str:
        return current_process().name

    @cached_property
    def _event_version_information(self) -> dict:
        return {
            "logprep": get_versions().get("version"),
            "configuration": self._logprep_config.get("version", "unset"),
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
        pipeline = [self._create_processor(entry) for entry in self._logprep_config.get("pipeline")]
        self.logger.debug("Finished building pipeline")
        return pipeline

    @cached_property
    def _output(self) -> dict[str, Output]:
        output_configs = self._logprep_config.get("output")
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
        input_connector_config = self._logprep_config.get("input")
        connector_name = list(input_connector_config.keys())[0]
        input_connector_config[connector_name].update(
            {"version_information": self._event_version_information}
        )
        if input_connector_config is None:
            return None
        return Factory.create(input_connector_config, self.logger)

    @_handle_pipeline_error
    def _setup(self):
        self.logger.debug("Creating connectors")
        for _, output in self._output.items():
            output.input_connector = self._input
        self.logger.debug(
            f"Created connectors -> input: '{self._input.describe()}',"
            f" output -> '{[output.describe() for _, output in self._output.items()]}'"
        )
        self._input.pipeline_index = self.pipeline_index
        self._input.setup()
        for _, output in self._output.items():
            output.setup()

        if hasattr(self._input, "server"):
            while self._input.server.config.port in self._used_server_ports:
                self._input.server.config.port += 1
            self._used_server_ports.update({self._input.server.config.port: self._process_name})
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
        self._enable_iteration()
        assert self._input, "Pipeline should not be run without input connector"
        assert self._output, "Pipeline should not be run without output connector"
        with self._lock:
            with warnings.catch_warnings():
                warnings.simplefilter("default")
                self._setup()
        self.logger.debug("Start iterating")
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
        Component.run_pending_tasks()
        if self._processing_counter:
            self._processing_counter.scheduler.run_pending()
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

    @TimeMeasurement.measure_time(name="process_event")
    def process_event(self, event: dict):
        """process all processors for one event"""

        """
        ToDos:
            - TimeTracking
            - Processor Specific Metrics (Pseudonymizer, Amides, DomainResolver)
            - Fix Pseudonymizer str has no match
            - count number warnings/errors separatley or delete them from all metrics?
            - Tests
            - delete metric exposer
            - delete SharedCounter (Events in last 5 min: n)
            - create Grafana Dashboards
            - add pipelinemanager metrics (pipeline restarts)
            - clean up PrometheusExporter ("remove stale metric files" stil needed?)
            - add Kafka librdkafka metrics
            - count warnings
            - add version info to metrics
        """

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
        if self._processing_counter:
            self._processing_counter.increment()
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
        self.logger.debug(f"Stopping pipeline ({self._process_name})")
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False


class MultiprocessingPipeline(Process, Pipeline):
    """A thread-safe Pipeline for multiprocessing."""

    processed_counter: SharedCounter = SharedCounter()

    def __init__(
        self,
        pipeline_index: int,
        config: dict,
        log_queue: multiprocessing.Queue,
        lock: Lock,
        shared_dict: dict,
        used_server_ports: dict,
        prometheus_exporter: PrometheusStatsExporter = None,
    ) -> None:
        self._profile = config.get("profile_pipelines", False)

        Pipeline.__init__(
            self,
            pipeline_index=pipeline_index,
            config=config,
            counter=self.processed_counter,
            log_queue=log_queue,
            lock=lock,
            shared_dict=shared_dict,
            used_server_ports=used_server_ports,
            prometheus_exporter=prometheus_exporter,
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
