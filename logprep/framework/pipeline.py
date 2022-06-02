"""This module contains all Pipeline functionality.

Pipelines contain a list of processors that can be executed in order to process input log data.
They can be multi-processed.

"""
# pylint: disable=logging-fstring-interpolation
from ctypes import c_bool, c_double, c_ulonglong
from logging import DEBUG, INFO, NOTSET, Handler, Logger
from multiprocessing import Lock, Process, Value, current_process
from time import time
from typing import List

import json

from logprep.connector.connector_factory import ConnectorFactory
from logprep.input.input import (
    CriticalInputError,
    FatalInputError,
    SourceDisconnectedError,
    WarningInputError,
)
from logprep.output.output import CriticalOutputError, FatalOutputError, WarningOutputError
from logprep.processor.base.exceptions import ProcessingWarning, ProcessingWarningCollection
from logprep.processor.processor_factory import ProcessorFactory
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler
from logprep.util.pipeline_profiler import PipelineProfiler
from logprep.util.processor_stats import StatusTracker, StatusLoggerCollection
from logprep.util.time_measurement import TimeMeasurement


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

    def __init__(
        self,
        connector_config: dict,
        pipeline_config: List[dict],
        status_logger_config: dict,
        timeout: float,
        counter: "SharedCounter",
        log_handler: Handler,
        lock: Lock,
        shared_dict: dict,
        status_logger: StatusLoggerCollection = None,
    ):
        if not isinstance(log_handler, Handler):
            raise MustProvideALogHandlerError
        self._connector_config = connector_config
        self._pipeline_config = pipeline_config
        self._timeout = timeout
        self._log_handler = log_handler
        self._logger = None

        self._continue_iterating = False
        self._pipeline = []
        self._input = None
        self._output = None

        self._processing_counter = counter

        self._tracker = StatusTracker(shared_dict, status_logger_config, status_logger, lock)

    def _setup(self):
        self._create_logger()
        self._build_pipeline()
        self._tracker.set_pipeline(self._pipeline)
        self._create_connectors()

    def _build_pipeline(self):
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f"Building '{current_process().name}'")
        self._pipeline = []
        for entry in self._pipeline_config:
            processor = ProcessorFactory.create(entry, self._logger)
            self._pipeline.append(processor)
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug(f"Created '{processor}' processor ({current_process().name})")
            self._pipeline[-1].setup()
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f"Finished building pipeline ({current_process().name})")

    def _create_connectors(self):
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f"Creating connectors ({current_process().name})")
        self._input, self._output = ConnectorFactory.create(self._connector_config)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"Created input connector '{self._input.describe_endpoint()}' "
                f"({current_process().name})"
            )
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"Created output connector '{self._output.describe_endpoint()}' "
                f"({current_process().name})"
            )

        self._input.setup()
        self._output.setup()
        if self._logger.isEnabledFor(DEBUG):
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
        self._setup()
        self._enable_iteration()
        try:
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug("Start iterating (%s)", current_process().name)
            while self._iterate():
                self._retrieve_and_process_data()
        except SourceDisconnectedError:
            self._logger.warning(
                f"Lost or failed to establish connection to {self._input.describe_endpoint()}"
            )
        except FatalInputError as error:
            self._logger.error(f"Input {self._input.describe_endpoint()} failed: {error}")
        except FatalOutputError as error:
            self._logger.error(f"Output {self._output.describe_endpoint()} failed: {error}")

        self._shut_down()

    def _iterate(self):
        return self._continue_iterating

    def _enable_iteration(self):
        self._continue_iterating = True

    def _retrieve_and_process_data(self):
        event = {}
        try:
            self._tracker.print_aggregate()
            event = self._input.get_next(self._timeout)

            try:
                self._tracker.kafka_offset = self._input.current_offset
            except AttributeError:
                pass

            if event:
                self._process_event(event)
                self._processing_counter.increment()
                self._processing_counter.print_if_ready()
                if event:
                    self._output.store(event)
                    if self._logger.isEnabledFor(DEBUG):
                        self._logger.debug("Stored output")
        except SourceDisconnectedError as error:
            raise error
        except WarningInputError as error:
            self._logger.warning(
                f"An error occurred for input {self._input.describe_endpoint()}: {error}"
            )
        except WarningOutputError as error:
            self._logger.warning(
                f"An error occurred for output {self._output.describe_endpoint()}: {error}"
            )
        except CriticalInputError as error:
            msg = f"A critical error occurred for input {self._input.describe_endpoint()}: {error}"
            self._logger.error(msg)
            if error.raw_input:
                self._output.store_failed(msg, error.raw_input, event)
        except CriticalOutputError as error:
            msg = (
                f"A critical error occurred for output "
                f"{self._output.describe_endpoint()}: {error}"
            )
            self._logger.error(msg)
            if error.raw_input:
                self._output.store_failed(msg, error.raw_input, {})

    @TimeMeasurement.measure_time("pipeline")
    def _process_event(self, event: dict):
        self._tracker.increment_aggregation("processed")

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
                        f"A non-fatal error occurred for processor {processor.describe()} when processing an event: {error}"
                    )

                    self._tracker.add_warnings(error, processor)
                except ProcessingWarningCollection as error:
                    for warning in error.processing_warnings:
                        self._logger.warning(
                            "A non-fatal error occurred for processor %s when processing an event: %s",
                            processor.describe(),
                            warning,
                        )

                        self._tracker.add_warnings(warning, processor)

                if not event:
                    if self._logger.isEnabledFor(DEBUG):
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

            self._tracker.add_errors(error, processor)
        # pylint: enable=broad-except

    def _store_extra_data(self, extra_data: tuple):
        if self._logger.isEnabledFor(DEBUG):
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
        connector_config: dict,
        pipeline_config: List[dict],
        status_logger_config: dict,
        timeout: float,
        log_handler: Handler,
        print_processed_period: float,
        lock: Lock,
        shared_dict: dict,
        profile: bool = False,
        status_logger: StatusLoggerCollection = None,
    ):
        if not isinstance(log_handler, MultiprocessingLogHandler):
            raise MustProvideAnMPLogHandlerError

        self._profile = profile
        self.processed_counter.setup(print_processed_period, log_handler)

        Pipeline.__init__(
            self,
            connector_config,
            pipeline_config,
            status_logger_config,
            timeout,
            self.processed_counter,
            log_handler,
            lock,
            shared_dict,
            status_logger=status_logger,
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
