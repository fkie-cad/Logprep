"""This module contains functionality to manage pipelines via multi-processing."""

# pylint: disable=logging-fstring-interpolation

import logging
import logging.handlers
import multiprocessing
import multiprocessing.managers
import multiprocessing.queues
import random
import time

from attr import define, field

from logprep.abc.component import Component
from logprep.connector.http.input import HttpInput
from logprep.framework.pipeline import Pipeline
from logprep.metrics.exporter import PrometheusExporter
from logprep.metrics.metrics import CounterMetric
from logprep.util.configuration import Configuration
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger = logging.getLogger("Manager")


class ThrottlingQueue(multiprocessing.queues.Queue):
    """A queue that throttles the number of items that can be put into it."""

    wait_time_max = 0.00000001

    @property
    def wait_time(self) -> float:
        return float(self.qsize() * self._maxsize) * self.wait_time_max

    def put(self, obj, block=True, timeout=None, batch_size=1):
        if self.qsize() >= self._maxsize * 0.8:
            # logger.warning("Too many requests, waiting for %s seconds", self.wait_time)
            time.sleep(self.wait_time / batch_size)
        super().put(obj, block=block, timeout=timeout)


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
        self.restart_count = 0
        self.restart_timeout_ms = random.randint(100, 1000)
        self.metrics = self.Metrics(labels={"component": "manager"})
        self.loghandler = None
        if multiprocessing.current_process().name == "MainProcess":
            self._set_http_input_queue(configuration)
            self._setup_logging()
        self._pipelines: list[multiprocessing.Process] = []
        self._configuration = configuration

        prometheus_config = self._configuration.metrics
        if prometheus_config.enabled:
            self.prometheus_exporter = PrometheusExporter(prometheus_config)
        else:
            self.prometheus_exporter = None

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def _set_http_input_queue(self, configuration):
        """
        this workaround has to be done because the queue size is not configurable
        after initialization and the queue has to be shared between the multiple processes
        """
        input_config = next(iter(configuration.input.values()))
        is_http_input = input_config.get("type") == "http_input"
        if not is_http_input and HttpInput.messages is not None:
            return
        message_backlog_size = input_config.get("message_backlog_size", 15000)
        HttpInput.messages = ThrottlingQueue(
            maxsize=message_backlog_size, ctx=multiprocessing.get_context()
        )

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
                "Restarting failed pipeline on index %s " "with exit code: %s",
                pipeline_index,
                exit_code,
            )
        if self._configuration.restart_count < 0:
            return
        self.restart_count += 1
        time.sleep(self.restart_timeout_ms / 1000)
        self.restart_timeout_ms = self.restart_timeout_ms * 2

    def stop(self):
        """Stop processing any pipelines by reducing the pipeline count to zero."""
        self._decrease_to_count(0)
        if self.prometheus_exporter:
            self.prometheus_exporter.cleanup_prometheus_multiprocess_dir()

    def restart(self):
        """Restarts all pipelines"""
        self.set_count(0)
        self.set_count(self._configuration.process_count)
        if not self.prometheus_exporter:
            return
        if not self.prometheus_exporter.is_running:
            self.prometheus_exporter.run()

    def _create_pipeline(self, index) -> multiprocessing.Process:
        pipeline = Pipeline(pipeline_index=index, config=self._configuration)
        logger.info("Created new pipeline")
        process = multiprocessing.Process(
            target=pipeline.run, daemon=True, name=f"Pipeline-{index}"
        )
        process.stop = pipeline.stop
        process.start()
        return process
