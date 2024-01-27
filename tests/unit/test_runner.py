# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import json
import os
import uuid
from copy import deepcopy
from functools import partial
from logging import Logger
from pathlib import Path
from unittest import mock

import pytest
from pytest import raises
from requests.exceptions import HTTPError, SSLError

from logprep._version import get_versions
from logprep.runner import (
    CannotReloadWhenConfigIsUnsetError,
    MustConfigureBeforeRunningError,
    MustNotConfigureTwiceError,
    MustNotCreateMoreThanOneManagerError,
    Runner,
    UseGetRunnerToCreateRunnerSingleton,
)
from logprep.util.configuration import Configuration
from tests.testdata.metadata import (
    path_to_alternative_config,
    path_to_config,
    path_to_invalid_config,
)
from tests.unit.framework.test_pipeline_manager import PipelineManagerForTesting


class RunnerForTesting(Runner):
    def __init__(self):
        super().__init__(bypass_check_to_obtain_non_singleton_instance=True)

    def _create_manager(self):
        self._manager = PipelineManagerForTesting()


class LogprepRunnerTest:
    def setup_method(self, _):
        self.logger = Logger("test")

        self.runner = RunnerForTesting()
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
        runner.load_configuration([path_to_config])

        runner._create_manager()
        with raises(MustNotCreateMoreThanOneManagerError):
            runner._create_manager()

    def test_fails_when_calling_load_configuration_with_non_existing_path(self):
        with raises(FileNotFoundError):
            self.runner.load_configuration(["non-existing-file"])

    def test_fails_if_file_path_is_not_a_list(self):
        with raises(TypeError):
            self.runner.load_configuration("this-is-not-a-list")

    def test_fails_when_calling_load_configuration_more_than_once(self):
        self.runner.load_configuration([path_to_config])

        with raises(MustNotConfigureTwiceError):
            self.runner.load_configuration([path_to_config])

    def test_fails_when_called_without_configuring_first(self):
        with raises(MustConfigureBeforeRunningError):
            self.runner.start()

    @mock.patch("logprep.util.configuration.Configuration.verify")
    def test_load_configuration_calls_verify_on_config(self, mock_verify):
        self.runner.load_configuration([path_to_config])
        mock_verify.assert_called()

    def test_fails_when_calling_reload_configuration_when_config_is_unset(self):
        with raises(CannotReloadWhenConfigIsUnsetError):
            self.runner.reload()


@pytest.fixture(name="config_path", scope="function")
def fixture_config_path(tmp_path: Path) -> Path:
    config_path = tmp_path / uuid.uuid4().hex
    configuration = Configuration.from_sources([path_to_config])
    config_path.write_text(configuration.as_yaml())
    return config_path


@pytest.fixture(name="configuration")
def fixture_configuration(config_path: Path) -> Configuration:
    return Configuration.from_sources([str(config_path)])


@pytest.fixture(name="runner")
def fixture_runner(configuration: Configuration) -> Runner:
    runner = Runner.get_runner(configuration)
    runner._configuration = configuration
    return runner


class TestRunner:
    def test_runner_sets_configuration(self):
        configuration = Configuration.from_sources([path_to_config])
        runner = Runner.get_runner(configuration)
        assert isinstance(runner._configuration, Configuration)
        assert runner._configuration == configuration

    def test_get_runner_returns_the_same_runner_on_all_calls(self):
        configuration = Configuration.from_sources([path_to_config])
        runner = Runner.get_runner(configuration)

        for _ in range(10):
            assert runner is Runner.get_runner(configuration)

    @mock.patch("logging.Logger.info")
    def test_reload_configuration_logs_info_when_reloading_config_was_successful(
        self, mock_info, runner
    ):
        with mock.patch.object(runner._manager, "restart"):
            runner.metrics.number_of_config_refreshes = 0
            runner._configuration.version = "very old version"
            runner.reload_configuration()
            mock_info.assert_has_calls([mock.call("Successfully reloaded configuration")])
            assert runner.metrics.number_of_config_refreshes == 1

    @mock.patch("logging.Logger.info")
    def test_reload_configuration_logs_info_if_config_does_not_change(self, mock_info, runner):
        runner.metrics.number_of_config_refreshes = 0
        runner.metrics.number_of_config_refresh_failures = 0
        runner.reload_configuration()
        mock_info.assert_has_calls([mock.call("Configuration version did not change")])
        assert runner.metrics.number_of_config_refreshes == 0
        assert runner.metrics.number_of_config_refresh_failures == 0

    @mock.patch("logging.Logger.error")
    def test_reload_configuration_logs_error_on_invalid_config(
        self, mock_error, runner, config_path
    ):
        runner.metrics.number_of_config_refreshes = 0
        runner.metrics.number_of_config_refresh_failures = 0
        config_path.write_text("invalid config")
        runner.reload_configuration()
        mock_error.assert_called()
        assert runner.metrics.number_of_config_refreshes == 0
        assert runner.metrics.number_of_config_refresh_failures == 1

    def test_reload_configuration_leaves_old_configuration_in_place_if_new_config_is_invalid(
        self, runner, config_path
    ):
        assert runner._configuration.version == "1"
        config_path.write_text("invalid config")
        runner.reload_configuration()
        assert runner._configuration.version == "1"

    def test_reload_invokes_manager_restart_on_config_change(self, runner: Runner):
        runner._configuration.version = "very old version"
        with mock.patch.object(runner._manager, "restart") as mock_restart:
            runner.reload_configuration()
        mock_restart.assert_called()

    @pytest.mark.parametrize(
        "new_value, expected_value",
        [(None, None), (0, 5), (1, 5), (2, 5), (3, 5), (10, 10), (42, 42)],
    )
    def test_set_config_refresh_interval(self, new_value, expected_value, runner):
        with mock.patch.object(runner, "_manager"):
            runner._config_refresh_interval = new_value
            runner._keep_iterating = partial(mock_keep_iterating, 1)
            runner.start()
            if expected_value is None:
                assert len(runner.scheduler.jobs) == 0
            else:
                assert runner.scheduler.jobs[0].interval == expected_value

    @mock.patch("schedule.Scheduler.run_pending")
    def test_iteration_calls_run_pending(self, mock_run_pending, runner):
        with mock.patch.object(runner, "_manager"):
            runner._keep_iterating = partial(mock_keep_iterating, 3)
            runner.start()
            mock_run_pending.call_count = 3

    @mock.patch("schedule.Scheduler.run_pending")
    def test_iteration_stops_if_continue_iterating_returns_false(self, mock_run_pending, runner):
        def patch_runner(runner):
            def patch():  # nosemgrep
                with runner._continue_iterating.get_lock():
                    runner._continue_iterating.value = False

            return patch

        mock_run_pending.side_effect = patch_runner(runner)
        runner.start()
        assert mock_run_pending.call_count == 1

    def test_reload_configuration_schedules_job_if_config_refresh_interval_is_set(
        self, runner: Runner, configuration: Configuration, config_path: Path
    ):
        runner.metrics.config_refresh_interval = 0
        assert len(runner.scheduler.jobs) == 0
        configuration.config_refresh_interval = 60
        config_path.write_text(configuration.as_yaml())
        runner._configuration.version = "very old version"
        with mock.patch.object(runner._manager, "restart"):
            runner.reload_configuration()
        assert len(runner.scheduler.jobs) == 1
        assert runner.metrics.config_refresh_interval == 60

    def test_reload_configuration_does_not_schedules_job_if_no_config_refresh_interval_is_set(
        self, runner: Runner
    ) -> None:
        assert len(runner.scheduler.jobs) == 0
        if runner._configuration.config_refresh_interval is not None:
            runner._configuration.config_refresh_interval = None
        runner.reload_configuration()
        assert len(runner.scheduler.jobs) == 0

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
        self.runner._configuration.paths = [str(config_path)]
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 5
        # second refresh with new refresh interval
        config_update.update({"config_refresh_interval": 10, "version": "newer version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._configuration.paths = [str(config_path)]
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
    def test_reload_configuration_sets_config_refresh_interval_metric_with_a_quarter_of_the_time(
        self, mock_get
    ):
        mock_get.side_effect = HTTPError(404)
        assert len(self.runner.scheduler.jobs) == 0
        self.runner._config_refresh_interval = 40
        self.runner.metrics.config_refresh_interval = 0
        self.runner.reload_configuration(refresh=True)
        assert self.runner.metrics.config_refresh_interval == 10

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
        self.runner._configuration.paths = [str(config_path)]
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
        self.runner._configuration.paths = [str(config_path)]
        with mock.patch("logprep.abc.getter.Getter.get") as mock_get:
            mock_get.side_effect = HTTPError(404)
            self.runner.reload_configuration(refresh=True)
            assert len(self.runner.scheduler.jobs) == 1
            assert self.runner.scheduler.jobs[0].interval == 5
        self.runner.reload_configuration(refresh=True)
        assert len(self.runner.scheduler.jobs) == 1
        assert self.runner.scheduler.jobs[0].interval == 12

    def test_reload_configuration_logs_new_version_and_sets_metric(self, tmp_path):
        assert len(self.runner.scheduler.jobs) == 0
        config_path = tmp_path / "config.yml"
        config_update = {"config_refresh_interval": 5, "version": "current version"}
        self.runner._configuration.update(config_update)
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 5, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._configuration.paths = [str(config_path)]
        with mock.patch("logging.Logger.info") as mock_info:
            with mock.patch("logprep.metrics.metrics.GaugeMetric.add_with_labels") as mock_add:
                self.runner.reload_configuration(refresh=True)
        mock_info.assert_called_with("Configuration version: new version")
        mock_add.assert_called()
        mock_add.assert_has_calls(
            (mock.call(1, {"logprep": f"{get_versions()['version']}", "config": "new version"}),)
        )

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
        self.runner._configuration.paths = [str(config_path)]
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

    @mock.patch(
        "logprep.framework.pipeline_manager.PrometheusExporter.cleanup_prometheus_multiprocess_dir"
    )
    def test_reload_configuration_does_not_call_prometheus_clean_up_method(
        self, prometheus, tmp_path, tmpdir
    ):
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(tmpdir)
        config_path = tmp_path / "config.yml"
        config_update = {
            "config_refresh_interval": 5,
            "version": "current version",
            "metrics": {"enabled": True},
        }
        self.runner._configuration.update(config_update)
        config_update = deepcopy(self.runner._configuration)
        config_update.update({"config_refresh_interval": 5, "version": "new version"})
        config_path.write_text(json.dumps(config_update))
        self.runner._yaml_path = str(config_path)
        self.runner.reload_configuration(refresh=True)
        prometheus.assert_not_called()
        del os.environ["PROMETHEUS_MULTIPROC_DIR"]

    def test_loop_restarts_failed_pipelines(self):
        self.runner._manager.set_configuration(self.runner._configuration)
        self.runner._manager.set_count(self.runner._configuration["process_count"])
        assert len(self.runner._manager._pipelines) == 3
        self.runner._manager._pipelines[1].process_is_alive = False
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.runner._loop()
        mock_warning.assert_called_once_with(
            "Restarted 1 failed pipeline(s), with exit code(s): [-1]"
        )
