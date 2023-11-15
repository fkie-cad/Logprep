"""This module contains functionality to manage pipelines via multi-processing."""
# pylint: disable=logging-fstring-interpolation

import logging
import logging.handlers
import multiprocessing

from attr import define, field

from logprep.abc.component import Component
from logprep.framework.pipeline import MultiprocessingPipeline
from logprep.metrics.exporter import PrometheusExporter
from logprep.metrics.metrics import CounterMetric
from logprep.util.configuration import Configuration


class PipelineManagerError(Exception):
    """Base class for pipeline related exceptions."""


class MustSetConfigurationFirstError(PipelineManagerError):
    """Raise if configuration was not set."""

    def __init__(self, what_failed: str):
        super().__init__(f"Failed to {what_failed}: Configuration is unset")


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

    def __init__(self):
        self.prometheus_exporter = None
        self.metrics = self.Metrics(labels={"component": "manager"})
        self._logger = logging.getLogger("Logprep PipelineManager")
        self.log_queue = multiprocessing.Queue(-1)
        self._queue_listener = logging.handlers.QueueListener(self.log_queue)
        self._queue_listener.start()

        self._pipelines = []
        self._configuration = None

        self._lock = multiprocessing.Lock()
        self._used_server_ports = None

    def set_configuration(self, configuration: Configuration):
        """set the verified config"""
        self._configuration = configuration

        manager = multiprocessing.Manager()
        self._used_server_ports = manager.dict()
        prometheus_config = configuration.get("metrics", {})
        if prometheus_config.get("enabled", False) and not self.prometheus_exporter:
            self.prometheus_exporter = PrometheusExporter(prometheus_config)

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
            self._pipelines[-1].start()
            self.metrics.number_of_pipeline_starts += 1

    def _decrease_to_count(self, count: int):
        while len(self._pipelines) > count:
            pipeline = self._pipelines.pop()
            pipeline.stop()
            pipeline.join()
            self.metrics.number_of_pipeline_stops += 1

    def restart_failed_pipeline(self):
        """Remove one pipeline at a time."""
        failed_pipelines = [pipeline for pipeline in self._pipelines if not pipeline.is_alive()]
        for failed_pipeline in failed_pipelines:
            self._pipelines.remove(failed_pipeline)
            self.metrics.number_of_failed_pipelines += 1
            if self.prometheus_exporter:
                self.prometheus_exporter.mark_process_dead(failed_pipeline.pid)

        if failed_pipelines:
            self.set_count(self._configuration.get("process_count"))
            exit_codes = [pipeline.exitcode for pipeline in failed_pipelines]
            self._logger.warning(
                f"Restarted {len(failed_pipelines)} failed pipeline(s), "
                f"with exit code(s): {exit_codes}"
            )

    def stop(self):
        """Stop processing any pipelines by reducing the pipeline count to zero."""
        self._decrease_to_count(0)
        if self.prometheus_exporter:
            self.prometheus_exporter.cleanup_prometheus_multiprocess_dir()

    def restart(self):
        """Restarts all pipelines"""
        self._decrease_to_count(0)
        self._increase_to_count(self._configuration.get("process_count"))

    def _create_pipeline(self, index) -> MultiprocessingPipeline:
        if self._configuration is None:
            raise MustSetConfigurationFirstError("create new pipeline")

        self._logger.info("Created new pipeline")
        return MultiprocessingPipeline(
            pipeline_index=index,
            config=self._configuration,
            log_queue=self.log_queue,
            lock=self._lock,
            used_server_ports=self._used_server_ports,
        )
