# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import uuid
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from logprep.runner import Runner
from logprep.util.configuration import Configuration
from logprep.util.defaults import EXITCODES
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

    def test_iteration_sets_error_queue_size(self, runner):
        with mock.patch.object(runner, "_manager") as mock_manager:
            mock_manager.restart_count = 0
            runner.metrics.number_of_events_in_error_queue = 0
            mock_manager.should_exit.side_effect = [False, False, True]
            mock_manager.error_queue.qsize.return_value = 42
            with pytest.raises(SystemExit):
                runner.start()
            assert (
                runner.metrics.number_of_events_in_error_queue == 84
            )  # because of mocking with int

    def test_iteration_calls_should_exit(self, runner):
        with mock.patch.object(runner, "_manager") as mock_manager:
            mock_manager.restart_count = 0
            mock_manager.should_exit.side_effect = [False, False, True]
            with pytest.raises(SystemExit):
                runner.start()
            mock_manager.should_exit.call_count = 3

    def test_stop_method(self, runner: Runner):
        assert not runner._exit_received
        runner.stop()
        assert runner._exit_received

    def test_stop_and_exit_calls_manager_stop(self, runner: Runner):
        runner._exit_received = True
        runner.start()
        with mock.patch.object(runner, "_manager") as mock_manager:
            runner.stop_and_exit()
        mock_manager.stop.assert_called()
        mock_manager.restart_failed_pipeline.assert_not_called()

    def test_stop_and_exit_is_register_atexit(self, configuration):
        with mock.patch("atexit.register") as mock_register:
            runner = Runner(configuration)
        mock_register.assert_called_with(runner.stop_and_exit)

    def test_metric_labels_returns_versions(self, runner: Runner):
        assert runner._metric_labels == {
            "logprep": f"{version('logprep')}",
            "config": runner._configuration.version,
        }

    def test_runner_exits_with_pipeline_error_exitcode_if_restart_count_exceeded(
        self, runner: Runner
    ):
        with mock.patch.object(runner, "_manager") as mock_manager:
            mock_manager.restart_count = 5
            with pytest.raises(SystemExit, match=str(EXITCODES.PIPELINE_ERROR.value)):
                runner.start()

    def test_runner_calls_reload_on_config_change(
        self, runner: Runner, configuration: Configuration
    ):
        with mock.patch.object(runner, "_manager") as mock_manager:
            mock_manager.reload = mock.Mock()
            runner._config_version = "old_version"
            configuration.version = "new_version"
            with pytest.raises(SystemExit):
                runner.start()
            mock_manager.reload.assert_called_once()
        assert runner._config_version == "new_version"
