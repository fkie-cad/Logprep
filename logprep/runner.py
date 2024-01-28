"""This module contains the logprep runner and is responsible for signal handling."""
# pylint: disable=logging-fstring-interpolation

import logging
from ctypes import c_bool
from multiprocessing import Value, current_process
from typing import Generator

import requests
from attrs import define, field
from schedule import Scheduler

from logprep._version import get_versions
from logprep.abc.component import Component
from logprep.framework.pipeline_manager import PipelineManager
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.util.configuration import (
    Configuration,
    ConfigVersionDidNotChangeError,
    InvalidConfigurationError,
)


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

    scheduler: Scheduler

    _runner = None

    _configuration: Configuration

    _metrics: "Runner.Metrics"

    scheduler: Scheduler

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """Metrics for the Logprep Runner."""

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
                    "could not be updated due to failures during the process."
                ),
                name="number_of_config_refreshes",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates how often the logprep configuration could not be updated
          due to failures during the process."""

    @property
    def _metric_labels(self) -> dict[str, str]:
        versions = get_versions()
        labels = {
            "logprep": f"{versions.get('version')}",
            "config": f"{self._configuration.version}",
        }
        return labels

    @property
    def _config_refresh_interval(self) -> int:
        """Indicates the configuration refresh interval in seconds."""
        return self._configuration.config_refresh_interval

    @_config_refresh_interval.setter
    def _config_refresh_interval(self, value: int|None) -> None:
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
        self._configuration = configuration
        self.metrics = self.Metrics(labels={"logprep": "unset", "config": "unset"})
        self._logger = logging.getLogger("Logprep Runner")

        self._manager = PipelineManager(configuration)
        self.scheduler = Scheduler()

        # noinspection PyTypeChecker
        self._continue_iterating = Value(c_bool)
        self._continue_iterating.value = False

    def start(self):
        """Start processing.

        This runs until an SIGTERM, SIGINT or KeyboardInterrupt signal is received, or an unhandled
        error occurs.
        """

        self._schedule_config_refresh_job()
        if self._manager.prometheus_exporter:
            self._manager.prometheus_exporter.run()
        self._logger.info("Startup complete")
        self._logger.debug("Runner iterating")
        for _ in self._keep_iterating():
            self.scheduler.run_pending()
            self._manager.restart_failed_pipeline()

    def reload_configuration(self):
        """Reloads the configuration"""
        try:
            self._configuration.reload()
            self._logger.info("Successfully reloaded configuration")
            self.metrics.number_of_config_refreshes += 1
            self._manager.restart()
            self._schedule_config_refresh_job()
            self._logger.info(f"Configuration version: {self._configuration.version}")
        except (requests.RequestException, FileNotFoundError) as error:
            self._logger.warning(f"Failed to load configuration: {error}")
            self.metrics.number_of_config_refresh_failures += 1
            self._config_refresh_interval = int(self._config_refresh_interval / 4)
            self._schedule_config_refresh_job()
        except ConfigVersionDidNotChangeError as error:
            self._logger.info(str(error))
        except InvalidConfigurationError as error:
            self._logger.error(str(error))
            self.metrics.number_of_config_refresh_failures += 1

    def stop(self):
        """Stop the current process"""
        if current_process().name == "MainProcess":
            if self._logger is not None:
                self._logger.info("Shutting down")
                self._logger.info("Initiated shutdown")
                self._manager.stop()
                self._logger.info("Shutdown complete")

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
        while 1:
            yield 1
