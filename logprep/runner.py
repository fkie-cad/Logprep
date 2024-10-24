"""This module contains the logprep runner and is responsible for signal handling."""

# pylint: disable=logging-fstring-interpolation

import atexit
import logging
import sys
from importlib.metadata import version
from typing import Generator

from attrs import define, field
from schedule import Scheduler

from logprep.abc.component import Component
from logprep.framework.pipeline_manager import PipelineManager
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.util.configuration import (
    ConfigGetterException,
    Configuration,
    ConfigVersionDidNotChangeError,
    InvalidConfigurationError,
)
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

    scheduler: Scheduler

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

        version_info: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Logprep version information",
                name="version_info",
                labels={"logprep": "unset", "config": "unset"},
                inject_label_values=False,
            )
        )
        """Logprep version info."""
        config_refresh_interval: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Logprep config refresh interval",
                name="config_refresh_interval",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates the configuration refresh interval in seconds."""
        number_of_config_refreshes: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Indicates how often the logprep configuration was updated.",
                name="number_of_config_refreshes",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates how often the logprep configuration was updated."""
        number_of_config_refresh_failures: CounterMetric = field(
            factory=lambda: CounterMetric(
                description=(
                    "Indicates how often the logprep configuration "
                    "could not be updated due to failures during the update."
                ),
                name="number_of_config_refreshes",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates how often the logprep configuration could not be updated
          due to failures during the update."""

    @property
    def _metric_labels(self) -> dict[str, str]:
        labels = {
            "logprep": f"{version('logprep')}",
            "config": f"{self._configuration.version}",
        }
        return labels

    @property
    def _config_refresh_interval(self) -> int:
        """Indicates the configuration refresh interval in seconds."""
        return self._configuration.config_refresh_interval

    @_config_refresh_interval.setter
    def _config_refresh_interval(self, value: int | None) -> None:
        """Set the configuration refresh interval in seconds."""
        if value is None:
            self._configuration.config_refresh_interval = None
        elif value <= 5:
            self._configuration.config_refresh_interval = 5
        else:
            self._configuration.config_refresh_interval = value

    # Use this method to obtain a runner singleton for production
    @staticmethod
    def get_runner(configuration: Configuration) -> "Runner":
        """Create a Runner singleton."""
        if Runner._runner is None:
            Runner._runner = Runner(configuration)
        return Runner._runner

    # For production, use the get_runner method to create/get access to a singleton!
    def __init__(self, configuration: Configuration) -> None:
        self._manager: PipelineManager | None = None
        atexit.register(self.stop_and_exit)
        self.exit_code = EXITCODES.SUCCESS
        self._configuration = configuration
        self.metrics = self.Metrics(labels={"logprep": "unset", "config": "unset"})
        self._logger = logging.getLogger("Runner")
        self._manager = PipelineManager(configuration)
        self.scheduler = Scheduler()

    def start(self):
        """Start processing.

        This runs until an SIGTERM, SIGINT or KeyboardInterrupt signal is received, or an unhandled
        error occurs.
        """
        self._set_version_info_metric()
        self._schedule_config_refresh_job()
        self._manager.start()
        self._logger.info("Startup complete")
        self._logger.debug("Runner iterating")
        self._iterate()

    def stop_and_exit(self):
        """Stop the runner and exit the process."""
        self._logger.info("Shutting down")
        if self._manager:
            self._manager.stop()

    def _iterate(self):
        for _ in self._keep_iterating():
            if self._exit_received:
                break
            self.scheduler.run_pending()
            if self._manager.should_exit():
                self.exit_code = EXITCODES.PIPELINE_ERROR.value
                self._logger.error("Restart count exceeded. Exiting.")
                sys.exit(self.exit_code)
            if self._manager.error_queue is not None:
                self.metrics.number_of_events_in_error_queue += self._manager.error_queue.qsize()
            self._manager.restart_failed_pipeline()

    def reload_configuration(self):
        """Reloads the configuration"""
        try:
            self._configuration.reload()
            self._logger.info("Successfully reloaded configuration")
            self.metrics.number_of_config_refreshes += 1
            self._manager.reload()
            self._schedule_config_refresh_job()
            self._logger.info(f"Configuration version: {self._configuration.version}")
            self._set_version_info_metric()
        except ConfigGetterException as error:
            self._logger.warning(f"Failed to load configuration: {error}")
            self.metrics.number_of_config_refresh_failures += 1
            self._config_refresh_interval = int(self._config_refresh_interval / 4)
            self._schedule_config_refresh_job()
        except ConfigVersionDidNotChangeError as error:
            self._logger.info(str(error))
        except InvalidConfigurationError as error:
            self._logger.error(str(error))
            self.metrics.number_of_config_refresh_failures += 1

    def _set_version_info_metric(self):
        self.metrics.version_info.add_with_labels(
            1,
            {"logprep": f"{version('logprep')}", "config": self._configuration.version},
        )

    def stop(self):
        """Stop the logprep runner. Is called by the signal handler
        in run_logprep.py."""
        self._exit_received = True

    def _schedule_config_refresh_job(self):
        refresh_interval = self._config_refresh_interval
        scheduler = self.scheduler
        if scheduler.jobs:
            scheduler.cancel_job(scheduler.jobs[0])
        if isinstance(refresh_interval, (float, int)):
            self.metrics.config_refresh_interval += refresh_interval
            scheduler.every(refresh_interval).seconds.do(self.reload_configuration)
            self._logger.info(f"Config refresh interval is set to: {refresh_interval} seconds")

    def _keep_iterating(self) -> Generator:
        """Indicates whether the runner should keep iterating."""

        while 1:  # pragma: no cover
            yield 1
