"""This module contains functionality to manage pipelines via multi-processing."""

# pylint: disable=logging-fstring-interpolation

import logging
import logging.handlers
import multiprocessing
import multiprocessing.queues

from attr import define, field

from logprep.abc.component import Component
from logprep.connector.http.input import HttpConnector
from logprep.framework.pipeline import Pipeline
from logprep.metrics.exporter import PrometheusExporter
from logprep.metrics.metrics import CounterMetric
from logprep.util.configuration import Configuration


def logger_process(queue: multiprocessing.queues.Queue, logger: logging.Logger):
    """Process log messages from a queue."""

    while True:
        message = queue.get()
        if message is None:
            break
        logger.handle(message)


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
        self.metrics = self.Metrics(labels={"component": "manager"})
        self._logger = logging.getLogger("PipelineManager")
        if multiprocessing.current_process().name == "MainProcess":
            self._start_multiprocess_logger()
            self._set_http_input_queue(configuration)
        self._pipelines: list[multiprocessing.Process] = []
        self._configuration = configuration

        self._lock = multiprocessing.Lock()
        prometheus_config = self._configuration.metrics
        if prometheus_config.enabled:
            self.prometheus_exporter = PrometheusExporter(prometheus_config)
        else:
            self.prometheus_exporter = None

    def _set_http_input_queue(self, configuration):
        """
        this workaround has to be done because the queue size is not configurable
        after initialization and the queue has to be shared between the multiple processes
        """
        input_config = next(iter(configuration.input.values()))
        is_http_input = input_config.get("type") == "http_input"
        if not is_http_input and HttpConnector.messages is not None:
            return
        message_backlog_size = input_config.get("message_backlog_size", 15000)
        HttpConnector.messages = multiprocessing.Queue(maxsize=message_backlog_size)

    def _start_multiprocess_logger(self):
        self.log_queue = multiprocessing.Queue(-1)
        self._log_process = multiprocessing.Process(
            target=logger_process, args=(self.log_queue, self._logger), daemon=True
        )
        self._log_process.start()

    def get_count(self) -> int:
        """Get the pipeline count.

        Parameters
        ----------
        count : int
           The pipeline count will be incrementally changed until it reaches this value.

        """
        self._logger.debug(f"Getting pipeline count: {len(self._pipelines)}")
        return len(self._pipelines)

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
            return

        for index, failed_pipeline in failed_pipelines:
            pipeline_index = index + 1
            self._pipelines.pop(index)
            self.metrics.number_of_failed_pipelines += 1
            if self.prometheus_exporter:
                self.prometheus_exporter.mark_process_dead(failed_pipeline.pid)
            self._pipelines.insert(index, self._create_pipeline(pipeline_index))
            exit_code = failed_pipeline.exitcode
            self._logger.warning(
                f"Restarting failed pipeline on index {pipeline_index} "
                f"with exit code: {exit_code}"
            )

    def stop(self):
        """Stop processing any pipelines by reducing the pipeline count to zero."""
        self._decrease_to_count(0)
        if self.prometheus_exporter:
            self.prometheus_exporter.cleanup_prometheus_multiprocess_dir()
        self.log_queue.put(None)  # signal the logger process to stop
        self._log_process.join()
        self.log_queue.close()

    def restart(self):
        """Restarts all pipelines"""
        self.set_count(0)
        self.set_count(self._configuration.process_count)
        if not self.prometheus_exporter:
            return
        if not self.prometheus_exporter.is_running:
            self.prometheus_exporter.run()

    def _create_pipeline(self, index) -> multiprocessing.Process:
        pipeline = Pipeline(
            pipeline_index=index,
            config=self._configuration,
            log_queue=self.log_queue,
            lock=self._lock,
        )
        self._logger.info("Created new pipeline")
        process = multiprocessing.Process(target=pipeline.run, daemon=True)
        process.stop = pipeline.stop
        process.start()
        return process
