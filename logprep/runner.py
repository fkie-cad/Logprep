"""This module contains the logprep runner and is responsible for signal handling."""

# pylint: disable=logging-fstring-interpolation

import atexit
import logging
import sys
from importlib.metadata import version
from typing import Generator

from attrs import define, field

from logprep.abc.component import Component
from logprep.framework.pipeline_manager import PipelineManager
from logprep.metrics.metrics import GaugeMetric
from logprep.util.configuration import Configuration
from logprep.util.defaults import EXITCODES


class Runner:
    """Provide the main entry point.

    As a user, you will usually only interact with this class.

    For production use, there should only be one runner. Use Runner.get_runner() to obtain that
    runner. Then, you should set a logger (from the Python library's logging package) and load the
    configuration (a YAML file, see documentation for details). Finally, call the start method
    to start processing.

    Example
    -------
    For a complete example take a Look at run_logprep.py - for simply getting a Runner started
    this should suffice:

    >>> configuration = Configuration.from_sources(["path/to/config.yml"])
    >>> runner = Runner.get_runner(configuration)
    >>> runner.start()

    """

    _runner = None

    _configuration: Configuration

    _metrics: "Runner.Metrics"

    _exit_received: bool = False

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """Metrics for the Logprep Runner."""

        number_of_events_in_error_queue: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Current number of events in error queue",
                name="number_of_events_in_error_queue",
            )
        )
        """Current size of the error queue."""

    @property
    def _metric_labels(self) -> dict[str, str]:
        labels = {
            "logprep": f"{version('logprep')}",
            "config": f"{self._configuration.version}",
        }
        return labels

    # Use this method to obtain a runner singleton for production
    @staticmethod
    def get_runner(configuration: Configuration) -> "Runner":
        """Create a Runner singleton."""
        if Runner._runner is None:
            Runner._runner = Runner(configuration)
        return Runner._runner

    # For production, use the get_runner method to create/get access to a singleton!
    def __init__(self, configuration: Configuration) -> None:
        atexit.register(self.stop_and_exit)
        self.exit_code = EXITCODES.SUCCESS
        self._configuration = configuration
        self._config_version = self._configuration.version  # to trigger reloads
        self.metrics = self.Metrics(labels={"logprep": "unset", "config": "unset"})
        self._logger = logging.getLogger("Runner")
        self._manager = PipelineManager(configuration)

    def start(self) -> None:
        """Start processing.

        This runs until an SIGTERM, SIGINT or KeyboardInterrupt signal is received, or an unhandled
        error occurs.
        """
        self._configuration.schedule_config_refresh()
        self._manager.start()
        self._logger.info("Startup complete")
        self._logger.debug("Runner iterating")
        self._iterate()

    def stop_and_exit(self) -> None:
        """Stop the runner and exit the process."""
        self._logger.info("Shutting down")
        if self._manager:
            self._manager.stop()

    def _iterate(self) -> None:
        for _ in self._keep_iterating():
            if self._exit_received:
                break
            self._configuration.refresh()
            if self._configuration.version != self._config_version:
                self._manager.reload()
                self._config_version = self._configuration.version
            if self._manager.should_exit():
                self.exit_code = EXITCODES.PIPELINE_ERROR
                self._logger.error("Restart count exceeded. Exiting.")
                sys.exit(self.exit_code)
            if self._manager.error_queue is not None:
                self.metrics.number_of_events_in_error_queue += self._manager.error_queue.qsize()
            self._manager.restart_failed_pipeline()

    def stop(self) -> None:
        """Stop the logprep runner. Is called by the signal handler
        in run_logprep.py."""
        self._exit_received = True

    def _keep_iterating(self) -> Generator:
        """Indicates whether the runner should keep iterating."""

        while 1:  # pragma: no cover
            yield 1
