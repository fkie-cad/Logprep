# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import re
import uuid
from functools import partial
from pathlib import Path
from unittest import mock

import pytest
from requests.exceptions import HTTPError, SSLError

from logprep._version import get_versions
from logprep.runner import Runner
from logprep.util.configuration import Configuration
from tests.testdata.metadata import path_to_config


def mock_keep_iterating(iterations):
    for _ in range(iterations):
        yield True


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
    runner = Runner(configuration)  # we want to have a fresh runner for each test
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
        mock_info.assert_has_calls(
            [
                mock.call(
                    "Configuration version didn't change. Continue running with current version."
                )
            ]
        )
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

    def test_reload_configuration_reschedules_job_with_new_refresh_interval(
        self, runner: Runner, configuration: Configuration, config_path: Path
    ) -> None:
        assert len(runner.scheduler.jobs) == 0
        # first refresh
        configuration.config_refresh_interval = 5
        config_path.write_text(configuration.as_yaml())
        runner._configuration.version = "very old version"
        with mock.patch.object(runner._manager, "restart"):
            runner.reload_configuration()
        assert len(runner.scheduler.jobs) == 1
        assert runner.scheduler.jobs[0].interval == 5
        # second refresh with new refresh interval
        configuration.config_refresh_interval = 10
        config_path.write_text(configuration.as_yaml())
        runner._configuration.version = "even older version"
        with mock.patch.object(runner._manager, "restart"):
            runner.reload_configuration()
        assert len(runner.scheduler.jobs) == 1
        assert runner.scheduler.jobs[0].interval == 10

    @pytest.mark.parametrize(
        "exception, log_message",
        [
            (HTTPError(404), "404"),
            (
                FileNotFoundError("no such file or directory"),
                "One or more of the given config file(s) does not exist",
            ),
            (SSLError("SSL context"), "SSL context"),
        ],
    )
    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_logs_exception_and_schedules_new_refresh_with_a_quarter_the_time(
        self, mock_get, runner: Runner, caplog, exception, log_message
    ):
        mock_get.side_effect = exception
        assert len(runner.scheduler.jobs) == 0
        runner._config_refresh_interval = 40
        runner.reload_configuration()
        assert log_message in caplog.text
        assert len(runner.scheduler.jobs) == 1
        assert runner.scheduler.jobs[0].interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_sets_config_refresh_interval_metric_with_a_quarter_of_the_time(
        self, mock_get, runner: Runner
    ):
        mock_get.side_effect = HTTPError(404)
        assert len(runner.scheduler.jobs) == 0
        runner._config_refresh_interval = 40
        runner.metrics.config_refresh_interval = 0
        runner.reload_configuration()
        assert runner.metrics.config_refresh_interval == 10

    @mock.patch("logprep.abc.getter.Getter.get")
    def test_reload_configuration_does_not_set_refresh_interval_below_5_seconds(
        self, mock_get, caplog, runner: Runner
    ):
        mock_get.side_effect = HTTPError(404)
        assert len(runner.scheduler.jobs) == 0
        runner._config_refresh_interval = 12
        with caplog.at_level("INFO"):
            runner.reload_configuration()
        assert re.search(r"Failed to load configuration: .*404", caplog.text)
        assert re.search("Config refresh interval is set to: 5 seconds", caplog.text)
        assert len(runner.scheduler.jobs) == 1
        assert runner.scheduler.jobs[0].interval == 5

    def test_reload_configuration_sets_refresh_interval_on_successful_reload_after_request_exception(
        self, runner: Runner, config_path: Path
    ):
        runner._config_refresh_interval = 12
        new_config = Configuration.from_sources([str(config_path)])
        new_config.config_refresh_interval = 60
        new_config.version = "new version"
        config_path.write_text(new_config.as_yaml())
        with mock.patch("logprep.abc.getter.Getter.get") as mock_get:
            mock_get.side_effect = HTTPError(404)
            runner.reload_configuration()
            assert len(runner.scheduler.jobs) == 1
            assert runner.scheduler.jobs[0].interval == 5
        with mock.patch.object(runner._manager, "restart"):
            runner.reload_configuration()
        assert len(runner.scheduler.jobs) == 1
        assert runner.scheduler.jobs[0].interval == 60

    def test_reload_configuration_logs_new_version_and_sets_metric(
        self, runner: Runner, config_path: Path
    ):
        assert len(runner.scheduler.jobs) == 0
        new_config = Configuration.from_sources([str(config_path)])
        new_config.config_refresh_interval = 5
        version = str(uuid.uuid4().hex)
        new_config.version = version
        config_path.write_text(new_config.as_yaml())
        with mock.patch("logging.Logger.info") as mock_info:
            with mock.patch("logprep.metrics.metrics.GaugeMetric.add_with_labels") as mock_add:
                with mock.patch.object(runner._manager, "restart"):
                    runner.reload_configuration()
        mock_info.assert_called_with(f"Configuration version: {version}")
        mock_add.assert_called()
        mock_add.assert_has_calls(
            (mock.call(1, {"logprep": f"{get_versions()['version']}", "config": version}),)
        )

    def test_stop_method(self, runner: Runner):
        assert not runner._exit_received
        runner.stop()
        assert runner._exit_received

    @mock.patch("logprep.runner.Runner._keep_iterating", new=partial(mock_keep_iterating, 1))
    def test_start_sets_version_metric(self, runner: Runner):
        runner._configuration.version = "very custom version"
        with mock.patch("logprep.metrics.metrics.GaugeMetric.add_with_labels") as mock_add:
            runner.start()
        mock_add.assert_called()
        mock_add.assert_has_calls(
            (
                mock.call(
                    1,
                    {
                        "logprep": f"{get_versions()['version']}",
                        "config": runner._configuration.version,
                    },
                ),
            )
        )

    def test_start_calls_manager_stop_after_breaking_the_loop(self, runner: Runner):
        with mock.patch.object(runner, "_manager") as mock_manager:
            runner._exit_received = True
            runner.start()
        mock_manager.stop.assert_called()
        mock_manager.restart_failed_pipeline.assert_not_called()

    def test_metric_labels_returns_versions(self, runner: Runner):
        assert runner._metric_labels == {
            "logprep": f"{get_versions()['version']}",
            "config": runner._configuration.version,
        }
