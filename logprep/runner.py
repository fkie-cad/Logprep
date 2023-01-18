"""This module contains the logprep runner and is responsible for signal handling."""

import signal
from ctypes import c_bool
from logging import Logger
from multiprocessing import Value, current_process

import requests
from schedule import Scheduler

from logprep.framework.pipeline_manager import PipelineManager
from logprep.metrics.metric_targets import get_metric_targets
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler


class RunnerError(BaseException):
    """Base class for Runner related exceptions."""


class MustNotConfigureTwiceError(RunnerError):
    """Raise if the configuration has been set more than once."""


class NotALoggerError(RunnerError):
    """Raise if the logger was assigned a non-logger object ."""


class MustNotSetLoggerTwiceError(RunnerError):
    """Raise if a logger has been set more than once."""


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
    exceptions that are not catched by it. Hence, we recommend to simply catch BaseException and
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

    _runner = None

    scheduler: Scheduler

    # Use this method to obtain a runner singleton for production
    @staticmethod
    def get_runner():
        """Create a Runner singleton."""
        if Runner._runner is None:
            Runner._runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
        return Runner._runner

    # For production, use the get_runner method to create/get access to a singleton!
    def __init__(self, bypass_check_to_obtain_non_singleton_instance=False):
        self._configuration = None
        self._yaml_path = None
        self._logger = None
        self._metric_targets = None
        self._log_handler = None
        self._config_refresh_interval = None

        self._manager = None
        self.scheduler = Scheduler()

        # noinspection PyTypeChecker
        self._continue_iterating = Value(c_bool)
        self._continue_iterating.value = False

        if not bypass_check_to_obtain_non_singleton_instance:
            raise UseGetRunnerToCreateRunnerSingleton

    def set_logger(self, logger: Logger):
        """Setup logging for any "known" errors from any part of the software.

        Parameters
        ----------
        logger: Logger
            An instance of logging.Logger.

        Raises
        ------
        NotALoggerError
            If 'logger' is not an instance of Logger.
        MustNotSetLoggerTwiceError
            If 'self._logger' was already set.
        """
        if not isinstance(logger, Logger):
            raise NotALoggerError
        if self._logger is not None:
            raise MustNotSetLoggerTwiceError

        self._logger = logger
        self._log_handler = MultiprocessingLogHandler(logger.level)

    def load_configuration(self, yaml_file: str):
        """Load the configuration from a YAML file (cf. documentation).

        This will raise an exception if the configuration is not valid.

        Parameters
        ----------
        yaml_file: str
            Path to a configuration YAML file.

        Raises
        ------
        MustNotConfigureTwiceError
            If '_configuration' was already set.

        """
        if self._configuration is not None:
            raise MustNotConfigureTwiceError

        configuration = Configuration.create_from_yaml(yaml_file)
        configuration.verify(self._logger)

        self._yaml_path = yaml_file
        self._configuration = configuration
        self._config_refresh_interval = configuration.get("config_refresh_interval")

    def start(self):
        """Start processing.

        This runs until an SIGTERM, SIGINT or KeyboardInterrupt signal is received, or an unhandled
        error occurs.

        Raises
        ------
        MustConfigureBeforeRunningError
            If '_configuration' was not set before starting the Runner.
        MustConfigureALoggerError
            If '_logger' was not set before reloading the configuration.

        """
        if self._configuration is None:
            raise MustConfigureBeforeRunningError
        if self._logger is None:
            raise MustConfigureALoggerError

        self._create_manager()
        self._manager.set_configuration(self._configuration)
        self._manager.set_count(self._configuration["process_count"])
        self._logger.debug("Pipeline manager initiated")

        with self._continue_iterating.get_lock():
            self._continue_iterating.value = True
        self._schedule_config_refresh_job()
        self._logger.info("Startup complete")
        for _ in self._keep_iterating():
            self._loop()
        self.stop()

        self._logger.info("Initiated shutdown")
        self._manager.stop()
        self._logger.info("Shutdown complete")

    def _loop(self):
        self.scheduler.run_pending()
        self._logger.debug("Runner iterating")
        self._manager.restart_failed_pipeline()
        # Note: We are waiting half the timeout because when shutting down, we also have to
        # wait for the logprep's timeout before the shutdown is actually initiated.
        self._manager.handle_logs_into_logger(self._logger, self._configuration["timeout"] / 2.0)

    def reload_configuration(self, refresh=False):
        """Reload the configuration from the configured yaml path.

        Raises
        ------
        CannotReloadWhenConfigIsUnsetError
            If '_configuration' was never set before reloading the configuration.

        """
        if self._configuration is None:
            raise CannotReloadWhenConfigIsUnsetError
        try:
            new_configuration = Configuration.create_from_yaml(self._yaml_path)
            self._config_refresh_interval = new_configuration.get("config_refresh_interval")
            self._schedule_config_refresh_job()
        except (requests.RequestException, FileNotFoundError) as error:
            self._logger.warning(f"Failed to load configuration: {error}")
            current_refresh_interval = self._config_refresh_interval
            if isinstance(current_refresh_interval, (float, int)):
                new_refresh_interval = current_refresh_interval / 4
                self._config_refresh_interval = new_refresh_interval
            self._schedule_config_refresh_job()
            return
        if refresh:
            version_differ = new_configuration.get("version") != self._configuration.get("version")
            if not version_differ:
                self._logger.info(
                    "Configuration version didn't change. Continue running with current version."
                )
                self._logger.info(
                    f"Configuration version: {self._configuration.get('version', 'unset')}"
                )
                return
        try:
            new_configuration.verify(self._logger)

            # Only reached when configuration is verified successfully
            self._configuration = new_configuration
            self._schedule_config_refresh_job()
            self._manager.stop()
            self._manager.set_configuration(self._configuration)
            self._manager.set_count(self._configuration["process_count"])
            self._logger.info("Successfully reloaded configuration")
            self._logger.info(
                f"Configuration version: {self._configuration.get('version', 'unset')}"
            )
        except InvalidConfigurationError as error:
            self._logger.error(
                "Invalid configuration, leaving old configuration in place: "
                + self._yaml_path
                + ": "
                + str(error)
            )

    def _schedule_config_refresh_job(self):
        refresh_interval = self._config_refresh_interval
        scheduler = self.scheduler
        if scheduler.jobs:
            scheduler.cancel_job(scheduler.jobs[0])
        if isinstance(refresh_interval, (float, int)):
            refresh_interval = 5 if refresh_interval < 5 else refresh_interval
            scheduler.every(refresh_interval).seconds.do(self.reload_configuration, refresh=True)
            self._logger.info(f"Config refresh interval is set to: {refresh_interval} seconds")

    def _create_manager(self):
        if self._manager is not None:
            raise MustNotCreateMoreThanOneManagerError
        metric_targets = get_metric_targets(self._configuration, self._logger)
        self._manager = PipelineManager(self._logger, metric_targets)

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
