"""This module contains the logprep runner and is responsible for signal handling."""
# pylint: disable=logging-fstring-interpolation

import logging
import signal
from ctypes import c_bool
from multiprocessing import Value, current_process

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


class RunnerError(Exception):
    """Base class for Runner related exceptions."""


class MustNotConfigureTwiceError(RunnerError):
    """Raise if the configuration has been set more than once."""


class NotALoggerError(RunnerError):
    """Raise if the logger was assigned a non-logger object ."""


class MustConfigureALoggerError(RunnerError):
    """Raise if no logger has been configured."""


class MustConfigureBeforeRunningError(RunnerError):
    """Raise if the runner has been started before it has been configured."""


class MustNotCreateMoreThanOneManagerError(RunnerError):
    """Raise if more than once managers have been created."""


class CannotReloadWhenConfigIsUnsetError(RunnerError):
    """Raise if the configuration was reloaded but not set."""


class UseGetRunnerToCreateRunnerSingleton(RunnerError):
    """ "Raise if the runner was not created as a singleton."""


class Runner:
    """Provide the main entry point.

    As a user, you will usually only interact with this class.

    For production use, there should only be one runner. Use Runner.get_runner() to obtain that
    runner. Then, you should set a logger (from the Python library's logging package) and load the
    configuration (a YAML file, see documentation for details). Finally, call the start method
    to start processing.

    The Runner should only raise exceptions derived from RunnerError but other components may raise
    exceptions that are not catched by it. Hence, we recommend to simply catch Exception and
    log it as an unhandled exception.

    Example
    -------
    For a complete example take a Look at run_logprep.py - for simply getting a Runner started
    this should suffice:

    >>> runner = Runner.get_runner()
    >>> runner.set_logger(logging.getLogger())
    >>> runner.load_configuration(path_to_configuration)
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
    def _config_refresh_interval(self, value: int) -> None:
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
        self._config_refresh_interval = None

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

        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True

        for _ in self._keep_iterating():
            self._loop()

        self._schedule_config_refresh_job()
        # if self._manager.prometheus_exporter:
        #     self._manager.prometheus_exporter.run()
        # self._logger.info("Startup complete")
        # self._logger.debug("Runner iterating")
        # for _ in self._keep_iterating():
        #     self._loop()
        # self.stop()

        # self._logger.info("Initiated shutdown")
        # self._manager.stop()
        # self._logger.info("Shutdown complete")

    def _loop(self):
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

        # try:
        #     new_configuration = Configuration.from_sources(self._configuration.paths)
        #     new_configuration.verify()
        #     self._config_refresh_interval = new_configuration.config_refresh_interval
        #     self._schedule_config_refresh_job()
        # except (requests.RequestException, FileNotFoundError, InvalidConfigurationError) as error:
        #     self._logger.warning(f"Failed to load configuration: {error}")
        #     current_refresh_interval = self._config_refresh_interval
        #     if isinstance(current_refresh_interval, (float, int)):
        #         new_refresh_interval = current_refresh_interval / 4
        #         self._config_refresh_interval = new_refresh_interval
        #         self.metrics.config_refresh_interval += new_refresh_interval
        #     self._schedule_config_refresh_job()
        #     return
        # if refresh:
        #     version_differ = new_configuration.version != self._configuration.version
        #     if not version_differ:
        #         self._logger.info(
        #             "Configuration version didn't change. Continue running with current version."
        #         )
        #         self._logger.info(f"Configuration version: {self._configuration.version}")
        #         return
        # try:
        #     new_configuration.verify()

        #     # Only reached when configuration is verified successfully
        #     self._configuration = new_configuration
        #     self._schedule_config_refresh_job()
        #     self._manager.set_configuration(self._configuration)
        #     self._manager.restart()
        #     self._logger.info("Successfully reloaded configuration")
        #     config_version = self._configuration.version
        #     self._logger.info(f"Configuration version: {config_version}")
        #     self.metrics.version_info.add_with_labels(1, self._metric_labels)
        #     self.metrics.number_of_config_refreshes += 1
        #     if self._config_refresh_interval is not None:
        #         self.metrics.config_refresh_interval += self._config_refresh_interval
        # except InvalidConfigurationError as error:
        #     self._logger.error(
        #         "Invalid configuration, leaving old"
        #         f" configuration in place: {', '.join(self._configuration.paths)}: {str(error)}"
        #     )

    def _schedule_config_refresh_job(self):
        refresh_interval = self._config_refresh_interval
        scheduler = self.scheduler
        if scheduler.jobs:
            scheduler.cancel_job(scheduler.jobs[0])
        if isinstance(refresh_interval, (float, int)):
            self.metrics.config_refresh_interval += refresh_interval
            scheduler.every(refresh_interval).seconds.do(self.reload_configuration, refresh=True)
            self._logger.info(f"Config refresh interval is set to: {refresh_interval} seconds")

    def stop(self):
        """Stop the current process"""
        if current_process().name == "MainProcess":
            if self._logger is not None:
                self._logger.info("Shutting down")
        with self._continue_iterating.get_lock():
            self._continue_iterating.value = False

    def _keep_iterating(self):
        """generator function"""
        while True:
            with self._continue_iterating.get_lock():
                iterate = self._continue_iterating.value
                if not iterate:
                    return
                yield iterate


def signal_handler(signal_number: int, _):
    """Handle signals for stopping the runner and reloading the configuration."""
    if signal_number == signal.SIGUSR1:
        print("Info: Reloading config")
        Runner.get_runner().reload_configuration()
    else:
        Runner.get_runner().stop()


# Register signals
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGUSR1, signal_handler)
