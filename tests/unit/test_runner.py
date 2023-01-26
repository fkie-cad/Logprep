# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import json
from copy import deepcopy
from functools import partial
from logging import ERROR, INFO, Logger
from os.path import join, split
from unittest import mock

from pytest import raises
from requests.exceptions import SSLError, HTTPError

from logprep.processor.labeler.labeling_schema import LabelingSchemaError
from logprep.runner import (
    CannotReloadWhenConfigIsUnsetError,
    MustConfigureALoggerError,
    MustConfigureBeforeRunningError,
    MustNotConfigureTwiceError,
    MustNotCreateMoreThanOneManagerError,
    MustNotSetLoggerTwiceError,
    NotALoggerError,
    Runner,
    UseGetRunnerToCreateRunnerSingleton,
)
from logprep.util.configuration import InvalidConfigurationErrors
from tests.testdata.ConfigurationForTest import ConfigurationForTest
from tests.testdata.metadata import (
    path_to_alternative_config,
    path_to_config,
    path_to_invalid_config,
    path_to_invalid_rules,
    path_to_schema2,
)
from tests.unit.framework.test_pipeline_manager import PipelineManagerForTesting
from tests.util.testhelpers import AssertEmitsLogMessage, HandlerStub


class RunnerForTesting(Runner):
    def __init__(self):
        super().__init__(bypass_check_to_obtain_non_singleton_instance=True)

    def _create_manager(self):
        self._manager = PipelineManagerForTesting(self._logger, self._metric_targets)


class LogprepRunnerTest:
    def setup_method(self, _):
        self.handler = HandlerStub()
        self.logger = Logger("test")
        self.logger.addHandler(self.handler)

        self.runner = RunnerForTesting()
        self.runner.set_logger(self.logger)
        self.runner._create_manager()


def mock_keep_iterating(iterations):
    for _ in range(iterations):
        yield True


class TestRunnerExpectedFailures(LogprepRunnerTest):
    def test_init_fails_when_bypass_check_flag_is_not_set(self):
        with raises(UseGetRunnerToCreateRunnerSingleton):
            Runner()

    def test_fails_when_calling_create_manager_more_than_once(self):
        runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
        runner.set_logger(self.logger)
        runner.load_configuration(path_to_config)

        runner._create_manager()
        with raises(MustNotCreateMoreThanOneManagerError):
            runner._create_manager()

    def test_fails_when_calling_load_configuration_with_non_existing_path(self):
        with raises(FileNotFoundError):
            self.runner.load_configuration("non-existing-file")

    def test_fails_when_calling_load_configuration_more_than_once(self):
        self.runner.load_configuration(path_to_config)

        with raises(MustNotConfigureTwiceError):
            self.runner.load_configuration(path_to_config)

    def test_fails_when_called_without_configuring_first(self):
        with raises(MustConfigureBeforeRunningError):
            self.runner.start()

    def test_fails_when_setting_logger_to_non_logger_object(self):
        for non_logger in [None, "string", 123, 45.67, TestRunner()]:
            with raises(NotALoggerError):
                self.runner.set_logger(non_logger)

    def test_fails_when_setting_logger_twice(self):
        with raises(MustNotSetLoggerTwiceError):
            self.runner.set_logger(Logger("test"))

    def test_fails_when_starting_without_setting_logger_first(self):
        self.runner.load_configuration(path_to_config)
        self.runner._logger = None

        with raises(MustConfigureALoggerError):
            self.runner.start()

    def test_fails_when_rules_are_invalid(self):
        with raises(
            InvalidConfigurationErrors,
            match=r"Could not verify configuration for processor instance 'labelername', "
            r"because it has invalid rules\.",
        ):
            with ConfigurationForTest(
                inject_changes=[
                    {
                        "pipeline": {
                            1: {
                                "labelername": {
                                    "specific_rules": [path_to_invalid_rules],
                                    "generic_rules": [path_to_invalid_rules],
                                }
                            }
                        }
                    }
                ]
            ) as path:
                self.runner.load_configuration(path)

    def test_fails_when_schema_and_rules_are_inconsistent(self):
        with raises(LabelingSchemaError):
            with ConfigurationForTest(
                inject_changes=[{"pipeline": {1: {"labelername": {"schema": path_to_schema2}}}}]
            ) as path:
                self.runner.load_configuration(path)

    def test_fails_when_calling_reload_configuration_when_config_is_unset(self):
        with raises(CannotReloadWhenConfigIsUnsetError):
            self.runner.reload_configuration()


class TestRunner(LogprepRunnerTest):
    def setup_method(self, _):
        self.handler = HandlerStub()
        self.logger = Logger("test")
        self.logger.addHandler(self.handler)

        self.runner = RunnerForTesting()
        self.runner.set_logger(self.logger)
        self.runner.load_configuration(path_to_config)
        self.runner._create_manager()

    def test_get_runner_returns_the_same_runner_on_all_calls(self):
        runner = Runner.get_runner()

        for _ in range(10):
            assert runner == Runner.get_runner()

    def test_reload_configuration_logs_info_when_reloading_config_was_successful(self):
        with AssertEmitsLogMessage(self.handler, INFO, "Successfully reloaded configuration"):
            self.runner.reload_configuration()

    def test_reload_configuration_reduces_logprep_instance_count_to_new_value(self):
        self.runner._manager.set_count(3)

        self.runner._yaml_path = path_to_alternative_config
        self.runner.reload_configuration()
        assert self.runner._manager.get_count() == 2

    def test_reload_configuration_leaves_old_configuration_in_place_if_new_config_is_invalid(self):
        old_configuration = deepcopy(self.runner._configuration)

        self.runner._yaml_path = path_to_invalid_config
        self.runner.reload_configuration()

        assert self.runner._configuration == old_configuration

    def test_reload_configuration_logs_error_when_new_configuration_is_invalid(self):
        self.runner._yaml_path = path_to_invalid_config

        with AssertEmitsLogMessage(
            self.handler,
            ERROR,
            prefix="Invalid configuration, leaving old configuration in place: ",
        ):
            self.runner.reload_configuration()

    def test_reload_configuration_creates_new_logprep_instances_with_new_configuration(self):
        self.runner._manager.set_count(3)
        old_logprep_instances = list(self.runner._manager._pipelines)

        self.runner.reload_configuration()

        assert set(old_logprep_instances).isdisjoint(set(self.runner._manager._pipelines))
        assert len(self.runner._manager._pipelines) == 3

    def get_path(self, filename):
        return join(split(__path__), filename)

    def test_start_sets_config_refresh_interval_to_a_minimum_of_5_seconds(self):
        self.runner._keep_iterating = partial(mock_keep_iterating, 1)
        self.runner._config_refresh_interval = 0
        self.runner.start()
        assert self.runner.scheduler.jobs[0].interval == 5

    @mock.patch("schedule.Scheduler.run_pending")
    def test_iteration_calls_run_pending(self, mock_run_pending):
        self.runner._keep_iterating = partial(mock_keep_iterating, 1)
        self.runner.start()
        mock_run_pending.assert_called()

    @mock.patch("schedule.Scheduler.run_pending")
    def test_iteration_calls_run_pending_on_every_iteration(self, mock_run_pending):
        self.runner._keep_iterating = partial(mock_keep_iterating, 3)
        self.runner.start()
        assert mock_run_pending.call_count == 3

    @mock.patch("schedule.Scheduler.run_pending")
    def test_iteration_stops_if_continue_iterating_returns_false(self, mock_run_pending):
        def patch_runner(runner):
            def patch():  # nosemgrep
                with runner._continue_iterating.get_lock():
                    runner._continue_iterating.value = False

            return patch

        mock_run_pending.side_effect = patch_runner(self.runner)
        self.runner.start()
        assert mock_run_pending.call_count == 1

    def test_reload_configuration_does_not_schedules_job_if_no_config_refresh_interval_is_set(self):
        assert len(self.runner.scheduler.jobs) == 0
        if "config_refresh_interval" in self.runner._configuration:
            self.runner._configuration.pop("config_refresh_interval")
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 0

    def test_reload_configuration_schedules_job_if_config_refresh_interval_is_set(self, tmp_path):
        assert len(self.runner.scheduler.jobs) == 0
        config_path = tmp_path / "config.yml"
        config_update = {"config_refresh_interval": 5, "version": "current version"}
        self.runner._configuration.update(config_update)
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 5, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1

    def test_reload_configuration_reschedules_job_with_new_refresh_interval(self, tmp_path):
        assert len(self.runner.scheduler.jobs) == 0
        config_path = tmp_path / "config.yml"
        # set current state
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 5, "version": "current version"})
        self.runner._configuration.update(config_update)
        # first refresh
        config_update.update({"config_refresh_interval": 5, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 5
        # second refresh with new refresh interval
        config_update.update({"config_refresh_interval": 10, "version": "newer version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_logs_request_exception_and_schedules_new_refresh_with_a_quarter_the_time(
        self, mock_get
    ):
        mock_get.side_effect = HTTPError(404)
        assert len(self.runner.scheduler.jobs) == 0
        self.runner._config_refresh_interval = 40
        with mock.patch("logging.Logger.warning") as mock_warning:
            with mock.patch("logging.Logger.info") as mock_info:
                self.runner.reload_configuration(refresh=True)
        mock_warning.assert_called_with("Failed to load configuration: 404")
        mock_info.assert_called_with("Config refresh interval is set to: 10.0 seconds")
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_logs_filenotfounderror_and_schedules_new_refresh_with_a_quarter_the_time(
        self, mock_get
    ):
        mock_get.side_effect = FileNotFoundError("no such file or directory")
        assert len(self.runner.scheduler.jobs) == 0
        self.runner._config_refresh_interval = 40
        with mock.patch("logging.Logger.warning") as mock_warning:
            with mock.patch("logging.Logger.info") as mock_info:
                self.runner.reload_configuration(refresh=True)
        mock_warning.assert_called_with("Failed to load configuration: no such file or directory")
        mock_info.assert_called_with("Config refresh interval is set to: 10.0 seconds")
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_logs_sslerror_and_schedules_new_refresh_with_a_quarter_the_time(
        self, mock_get
    ):
        mock_get.side_effect = SSLError("SSL context")
        assert len(self.runner.scheduler.jobs) == 0
        self.runner._config_refresh_interval = 40
        with mock.patch("logging.Logger.warning") as mock_warning:
            with mock.patch("logging.Logger.info") as mock_info:
                self.runner.reload_configuration(refresh=True)
        mock_warning.assert_called_with("Failed to load configuration: SSL context")
        mock_info.assert_called_with("Config refresh interval is set to: 10.0 seconds")
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_does_not_set_refresh_interval_below_5_seconds(self, mock_get):
        mock_get.side_effect = HTTPError(404)
        assert len(self.runner.scheduler.jobs) == 0
        self.runner._config_refresh_interval = 12
        with mock.patch("logging.Logger.warning") as mock_warning:
            with mock.patch("logging.Logger.info") as mock_info:
                self.runner.reload_configuration(refresh=True)
        mock_warning.assert_called_with("Failed to load configuration: 404")
        mock_info.assert_called_with("Config refresh interval is set to: 5 seconds")
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 5

    def test_reload_configuration_sets_refresh_interval_on_successful_reload_after_request_exception(
        self, tmp_path
    ):
        self.runner._config_refresh_interval = 12
        config_path = tmp_path / "config.yml"
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 60, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        with mock.patch("logprep.abc.getter.Getter.get") as mock_get:
            mock_get.side_effect = HTTPError(404)
            self.runner.reload_configuration(refresh=True)
            assert len(self.runner.scheduler.jobs) == 1
            assert self.runner.scheduler.jobs[0].interval == 5
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 60

    def test_reload_configuration_sets_refresh_interval_after_request_exception_without_new_config(
        self, tmp_path
    ):
        config_update = {"config_refresh_interval": 12, "version": "current version"}
        self.runner._config_refresh_interval = 12
        self.runner._configuration.update(config_update)
        config_path = tmp_path / "config.yml"
        config_update = deepcopy(self.runner._configuration)
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        with mock.patch("logprep.abc.getter.Getter.get") as mock_get:
            mock_get.side_effect = HTTPError(404)
            self.runner.reload_configuration(refresh=True)
            assert len(self.runner.scheduler.jobs) == 1
            assert self.runner.scheduler.jobs[0].interval == 5
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 12

    def test_reload_configuration_logs_new_version(self, tmp_path):
        assert len(self.runner.scheduler.jobs) == 0
        config_path = tmp_path / "config.yml"
        config_update = {"config_refresh_interval": 5, "version": "current version"}
        self.runner._configuration.update(config_update)
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 5, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        with mock.patch("logging.Logger.info") as mock_info:
            self.runner.reload_configuration(refresh=True)
        mock_info.assert_called_with("Configuration version: new version")

    def test_reload_configuration_decreases_processes_after_increase(self, tmp_path):
        self.runner._manager.set_configuration(self.runner._configuration)
        self.runner._manager.set_count(self.runner._configuration["process_count"])
        assert self.runner._configuration.get("process_count") == 3
        assert len(self.runner._manager._pipelines) == 3
        config_update = {
            "config_refresh_interval": 5,
            "version": "current version",
        }
        self.runner._configuration.update(config_update)
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner._manager._pipelines) == 3
        config_path = tmp_path / "config.yml"
        self.runner._yaml_path = str(config_path)
        config_update = deepcopy(self.runner._configuration)
        config_update.update(
            {"config_refresh_interval": 5, "version": "new version", "process_count": 4}
        )
        config_path.write_text(json.dumps(config_update))
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner._manager._pipelines) == 4
        config_update.update(
            {"config_refresh_interval": 5, "version": "newer version", "process_count": 1}
        )
        config_path.write_text(json.dumps(config_update))
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner._manager._pipelines) == 1

    def test_loop_restarts_failed_pipelines(self):
        self.runner._manager.set_configuration(self.runner._configuration)
        self.runner._manager.set_count(self.runner._configuration["process_count"])
        assert len(self.runner._manager._pipelines) == 3
        self.runner._manager._pipelines[1].process_is_alive = False
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.runner._loop()
        mock_warning.assert_called_once_with("Restarted 1 failed pipeline(s)")
