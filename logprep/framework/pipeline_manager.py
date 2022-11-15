"""This module contains functionality to manage pipelines via multi-processing."""

from logging import Logger, DEBUG
from multiprocessing import Manager, Lock
from queue import Empty

from logprep.framework.pipeline import MultiprocessingPipeline
from logprep.metrics.metric import MetricTargets
from logprep.util.configuration import Configuration
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler


class PipelineManagerError(BaseException):
    """Base class for pipeline related exceptions."""


class MustSetConfigurationFirstError(PipelineManagerError):
    """Raise if configuration was not set."""

    def __init__(self, what_failed: str):
        super().__init__(f"Failed to {what_failed}: Configuration is unset")


class PipelineManager:
    """Manage pipelines via multi-processing."""

    def __init__(self, logger: Logger, metric_targets: MetricTargets):
        self._logger = logger
        self.metric_targets = metric_targets

        self._log_handler = MultiprocessingLogHandler(self._logger.level)

        self._pipelines = []
        self._configuration = None

        self._lock = Lock()
        self._shared_dict = None

    def set_configuration(self, configuration: Configuration):
        """Verify the configuration and set it in the pipeline manager."""
        configuration.verify(self._logger)
        self._configuration = configuration

        manager = Manager()
        self._shared_dict = manager.dict()
        for idx in range(configuration["process_count"]):
            self._shared_dict[idx] = None

    def get_count(self) -> int:
        """Get the pipeline count.

        Parameters
        ----------
        count : int
           The pipeline count will be incrementally changed until it reaches this value.

        """
        if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
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

    def _decrease_to_count(self, count: int):
        while len(self._pipelines) > count:
            pipeline = self._pipelines.pop()
            pipeline.stop()
            pipeline.join()

    def replace_pipelines(self):
        """Replace one pipeline at a time."""
        for index, _ in enumerate(self._pipelines):
            old_pipeline = self._pipelines[index]
            old_pipeline.stop()
            old_pipeline.join()

            self._pipelines[index] = self._create_pipeline(index)
            self._pipelines[index].start()

    def remove_failed_pipeline(self):
        """Remove one pipeline at a time."""
        failed_pipelines = []
        for pipeline in self._pipelines:
            if not pipeline.is_alive():
                failed_pipelines.append(pipeline)

        for failed_pipeline in failed_pipelines:
            self._pipelines.remove(failed_pipeline)

            if self.metric_targets and self.metric_targets.prometheus_target:
                self.metric_targets.prometheus_target.prometheus_exporter.remove_metrics_from_process(
                    failed_pipeline.pid
                )

        if failed_pipelines:
            self._logger.warning(f"Removed {len(failed_pipelines)} failed pipeline(s)")

    def handle_logs_into_logger(self, logger: Logger, timeout: float):
        """Handle logs."""
        try:
            logger.handle(self._log_handler.get(timeout))
            while True:
                logger.handle(self._log_handler.get(0.0))
        except Empty:
            pass

    def stop(self):
        """Stop processing any pipelines by reducing the pipeline count to zero."""
        self._decrease_to_count(0)

    def _create_pipeline(self, index) -> MultiprocessingPipeline:
        if self._configuration is None:
            raise MustSetConfigurationFirstError("create new pipeline")

        self._logger.info("Created new pipeline")
        return MultiprocessingPipeline(
            pipeline_index=index,
            config=self._configuration,
            log_handler=self._log_handler,
            lock=self._lock,
            shared_dict=self._shared_dict,
            metric_targets=self.metric_targets,
        )
