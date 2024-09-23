"""This module contains functionality to manage pipelines via multi-processing."""

# pylint: disable=logging-fstring-interpolation

import logging
import logging.handlers
import multiprocessing
import multiprocessing.managers
import multiprocessing.queues
import random
import time
from typing import Any, Callable

from attr import define, field, validators

from logprep.abc.component import Component
from logprep.abc.input import CriticalInputError
from logprep.abc.output import CriticalOutputError, Output
from logprep.connector.http.input import HttpInput
from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline, PipelineResult
from logprep.metrics.exporter import PrometheusExporter
from logprep.metrics.metrics import CounterMetric
from logprep.util.configuration import Configuration
from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE, EXITCODES
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger = logging.getLogger("Manager")


class ThrottlingQueue(multiprocessing.queues.Queue):
    """A queue that throttles the number of items that can be put into it."""

    wait_time = 5

    @property
    def consumed_percent(self) -> int:
        """Return the percentage of items consumed."""
        return int((self.qsize() / self.capacity) * 100)

    def __init__(self, ctx, maxsize):
        super().__init__(ctx=ctx, maxsize=maxsize)
        self.capacity = maxsize
        self.call_time = None

    def throttle(self, batch_size=1):
        """Throttle put by sleeping."""
        if self.consumed_percent > 90:
            sleep_time = max(
                self.wait_time, int(self.wait_time * self.consumed_percent / batch_size)
            )
            # sleep times in microseconds
            time.sleep(sleep_time / 1000)

    def put(self, obj, block=True, timeout=None, batch_size=1):
        """Put an obj into the queue."""
        self.throttle(batch_size)
        super().put(obj, block=block, timeout=timeout)


@define()
class ComponentQueueListener:
    """This forks a process and handles all items from the given queue into
    the specified callable. It uses a sentinel object to stop the process."""

    _queue: multiprocessing.queues.Queue = field(
        validator=validators.instance_of(multiprocessing.queues.Queue)
    )
    """The queue to listen to."""

    _target: Callable = field(validator=validators.instance_of(Callable))
    """The target callable to call with the items from the queue."""

    _sentinel: Any = field(default=None)
    """The sentinel object to stop the process. This has to implement identity comparison."""

    _process: multiprocessing.Process = field(init=False)
    """The process that is forked to listen to the queue."""

    def __attrs_post_init__(self):
        self._process = multiprocessing.Process(target=self._listen, daemon=True)

    def start(self):
        """Start the listener."""
        self._process.start()

    def _listen(self):
        while True:
            event = None
            item = self._queue.get()
            if item is self._sentinel:
                break
            elif isinstance(item, PipelineResult):
                event = {"event": item.event, "errors": str(item.errors)}
            elif isinstance(item, (CriticalInputError, CriticalOutputError)):
                event = {"event": item.raw_input, "errors": str(item)}
            else:
                event = {"event": item, "errors": "An unknown error occurred"}
            self._target(event)

    def stop(self):
        """Stop the listener."""
        self._queue.put(self._sentinel)
        self._process.join()
        self._queue.close()


class PipelineManager:
    """Manage pipelines via multi-processing."""

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """Metrics for the PipelineManager."""

        number_of_pipeline_starts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of pipeline starts",
                name="number_of_pipeline_starts",
                labels={"component": "manager"},
                inject_label_values=False,
            )
        )
        """Number of pipeline starts"""
        number_of_pipeline_stops: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of pipeline stops",
                name="number_of_pipeline_stops",
            )
        )
        """Number of pipeline stops"""
        number_of_failed_pipelines: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of failed pipelines",
                name="number_of_failed_pipelines",
            )
        )
        """Number of failed pipelines"""

    def __init__(self, configuration: Configuration):
        self.restart_count: int = 0
        self.restart_timeout_ms: int = random.randint(100, 1000)
        self.metrics = self.Metrics(labels={"component": "manager"})
        self.loghandler: LogprepMPQueueListener = None
        self._error_queue: multiprocessing.Queue | None = None
        self._configuration: Configuration = configuration
        self._pipelines: list[multiprocessing.Process] = []
        self.prometheus_exporter: PrometheusExporter | None = None
        if multiprocessing.current_process().name == "MainProcess":
            self._setup_logging()
            self._setup_error_queue()
            self._setup_prometheus_exporter()
            self._set_http_input_queue()

    def _setup_prometheus_exporter(self):
        prometheus_config = self._configuration.metrics
        if prometheus_config.enabled and not self.prometheus_exporter:
            self.prometheus_exporter = PrometheusExporter(prometheus_config)
            self.prometheus_exporter.prepare_multiprocessing()

    def _setup_error_queue(self):
        if not self._configuration.error_output:
            return
        message_backlog_size = self._configuration.error_output.get(
            "message_backlog_size", DEFAULT_MESSAGE_BACKLOG_SIZE
        )
        self._error_output = Factory.create(self._configuration.error_output)
        self._error_queue = ThrottlingQueue(multiprocessing.get_context(), message_backlog_size)
        while 1:
            try:
                self._error_output.setup()
            except SystemExit as error:
                if self._configuration.restart_count < 0:
                    logger.warning(
                        "Error output not reachable and restart count < 1. Try again infinite..."
                    )
                    continue
                if self.should_exit():
                    logger.error("Error output not reachable. Exiting...")
                    self.stop()
                    raise SystemExit(EXITCODES.ERROR_OUTPUT_NOT_REACHABLE.value) from error
                self._wait_to_restart()
                logger.warning("Error output not reachable. Trying again...")
            if self._error_output.health():
                break

        self._error_listener = ComponentQueueListener(self._error_queue, self._error_output.store)
        self._error_listener.start()

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def _set_http_input_queue(self):
        """
        this workaround has to be done because the queue size is not configurable
        after initialization and the queue has to be shared between the multiple processes
        """
        input_config = list(self._configuration.input.values())
        input_config = input_config[0] if input_config else {}
        is_http_input = input_config.get("type") == "http_input"
        if not is_http_input and HttpInput.messages is not None:
            return
        message_backlog_size = input_config.get(
            "message_backlog_size", DEFAULT_MESSAGE_BACKLOG_SIZE
        )
        HttpInput.messages = ThrottlingQueue(multiprocessing.get_context(), message_backlog_size)

    def set_count(self, count: int):
        """Set the pipeline count.

        Parameters
        ----------
        count : int
           The pipeline count will be incrementally changed until it reaches this value.

        """
        if count < len(self._pipelines):
            self._decrease_to_count(count)
        else:
            self._increase_to_count(count)

    def _increase_to_count(self, count: int):
        while len(self._pipelines) < count:
            new_pipeline_index = len(self._pipelines) + 1
            self._pipelines.append(self._create_pipeline(new_pipeline_index))
            self.metrics.number_of_pipeline_starts += 1

    def _decrease_to_count(self, count: int):
        while len(self._pipelines) > count:
            pipeline_process = self._pipelines.pop()
            pipeline_process.stop()
            pipeline_process.join()
            self.metrics.number_of_pipeline_stops += 1

    def restart_failed_pipeline(self):
        """Remove one pipeline at a time."""
        failed_pipelines = [
            (index, pipeline)
            for index, pipeline in enumerate(self._pipelines)
            if not pipeline.is_alive()
        ]

        if not failed_pipelines:
            self.restart_count = 0
            return

        for index, failed_pipeline in failed_pipelines:
            pipeline_index = index + 1
            self._pipelines.pop(index)
            self.metrics.number_of_failed_pipelines += 1
            if self.prometheus_exporter:
                self.prometheus_exporter.mark_process_dead(failed_pipeline.pid)
            self._pipelines.insert(index, self._create_pipeline(pipeline_index))
            exit_code = failed_pipeline.exitcode
            logger.warning(
                "Restarting failed pipeline on index %s with exit code: %s",
                pipeline_index,
                exit_code,
            )
        if self._configuration.restart_count < 0:
            return
        self._wait_to_restart()

    def _wait_to_restart(self):
        self.restart_count += 1
        time.sleep(self.restart_timeout_ms / 1000)
        self.restart_timeout_ms = self.restart_timeout_ms * 2

    def stop(self):
        """Stop processing any pipelines by reducing the pipeline count to zero."""
        self.set_count(0)
        if self.prometheus_exporter:
            self.prometheus_exporter.server.shut_down()
            self.prometheus_exporter.cleanup_prometheus_multiprocess_dir()
        logger.info("Shutdown complete")
        if self.loghandler is not None:
            self.loghandler.stop()

    def start(self):
        """Start processing."""
        self.set_count(self._configuration.process_count)

    def restart(self):
        """Restarts all pipelines"""
        self.stop()
        self.start()

    def reload(self):
        self.set_count(0)
        self.set_count(self._configuration.process_count)

    def _create_pipeline(self, index) -> multiprocessing.Process:
        pipeline = Pipeline(
            pipeline_index=index,
            config=self._configuration,
            error_queue=self._error_queue,
        )
        if pipeline.pipeline_index == 1 and self.prometheus_exporter:
            self.prometheus_exporter.update_healthchecks(pipeline.get_health_functions())
        process = multiprocessing.Process(
            target=pipeline.run, daemon=True, name=f"Pipeline-{index}"
        )
        process.stop = pipeline.stop
        process.start()
        logger.info("Created new pipeline")
        return process

    def should_exit(self) -> bool:
        """Check if the manager should exit."""
        return all(
            (
                self._configuration.restart_count >= 0,
                self.restart_count >= self._configuration.restart_count,
            )
        )
