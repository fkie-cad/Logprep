# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import sys
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest
import requests
import responses
from click.testing import CliRunner

from logprep import run_ng
from logprep.ng.util.configuration import Configuration, InvalidConfigurationError
from logprep.ng.util.defaults import EXITCODES
from logprep.run_ng import cli


class TestRunLogprepNGCli:
    def setup_method(self):
        self.cli_runner = CliRunner()

    @pytest.mark.parametrize(
        "command, target",
        [
            ("run tests/testdata/config/config-ng.yml", "logprep.run_ng.Runner.run"),
            (
                "run tests/testdata/config/config-ng.yml tests/testdata/config/config-ng.yml",
                "logprep.run_ng.Runner.run",
            ),
        ],
    )
    def test_cli_commands_with_configs(self, command: str, target: str):
        with mock.patch(target) as mocked_target:
            result = self.cli_runner.invoke(cli, command.split())
        mocked_target.assert_called()
        assert result.exit_code == 0, f"{result.exc_info}"

    @pytest.mark.parametrize(
        "command",
        [
            ("run",),
        ],
    )
    def test_cli_invokes_default_config_location(self, command, caplog):
        result = self.cli_runner.invoke(cli, [*command])
        assert result.exit_code != 0
        assert "does not exist: /etc/logprep/pipeline.yml" in caplog.text

    def test_cli_run_starts_runner_with_config(self):
        config_file_path = ("tests/testdata/config/config-ng.yml",)
        expected_config = Configuration.from_sources(config_file_path)
        with mock.patch("logprep.run_ng.Runner") as mock_runner:
            args = ["run", *config_file_path]
            result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        mock_runner.assert_called_with(expected_config)

    def test_cli_run_starts_runner_with_multiple_configs(self):
        config_file_path = (
            "tests/testdata/config/config-ng.yml",
            "tests/testdata/config/config2-ng.yml",
        )
        expected_config = Configuration.from_sources(config_file_path)
        processor_name, processor_config = expected_config.pipeline[-1].popitem()
        assert processor_name == "expected_dissector"
        assert processor_config["type"] == "ng_dissector"
        with mock.patch("logprep.run_ng.Runner") as mock_runner:
            args = ["run", *config_file_path]
            result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        mock_runner.assert_called_with(expected_config)

    def test_exits_after_getter_error_for_not_existing_protocol(self, caplog):
        args = ["run", "almighty_protocol://tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value
        assert "No getter for protocol 'almighty_protocol'" in caplog.text

    def test_version_arg_prints_logprep_version(self):
        result = self.cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert "configuration version:   no configuration found" in result.output

    def test_run_version_arg_prints_logprep_version_with_config_version(self):
        args = ["run", "--version", "tests/testdata/config/config-ng.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert (
            "configuration version:   1, file://tests/testdata/config/config-ng.yml"
            in result.output
        )

    def test_run_version_arg_prints_logprep_version_without_config_value(self):
        args = ["run", "--version", "tests/testdata/config/config2-ng.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert (
            "configuration version:   alternative, file://tests/testdata/config/config2-ng.yml"
            in result.output
        )

    @responses.activate
    def test_run_version_arg_prints_with_http_config(self):
        config_path = "tests/testdata/config/config-ng.yml"
        responses.add(
            responses.GET,
            f"http://localhost:32000/{config_path}",
            Path(config_path).read_text(encoding="utf8"),
        )
        args = ["run", "--version", f"http://localhost:32000/{config_path}"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output

    @responses.activate
    def test_run_version_arg_prints_with_http_config_without_exposing_secret_data(self):
        config_path = "tests/testdata/config/config-ng.yml"
        mock_env = {
            "LOGPREP_CONFIG_AUTH_USERNAME": "username",
            "LOGPREP_CONFIG_AUTH_PASSWORD": "password",
        }
        responses.add(
            responses.GET,
            f"http://localhost:32000/{config_path}",
            Path(config_path).read_text(encoding="utf8"),
        )
        args = ["run", "--version", f"http://localhost:32000/{config_path}"]
        with mock.patch("os.environ", mock_env):
            result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output
        assert "username" not in result.output
        assert "password" not in result.output

    def test_run_no_config_error_is_printed_if_given_config_file_does_not_exist(self, caplog):
        non_existing_config_file = "/tmp/does/not/exist.yml"
        result = self.cli_runner.invoke(cli, ["run", non_existing_config_file])
        assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value
        expected_lines = (
            f"One or more of the given config file(s) does not exist: "
            f"{non_existing_config_file}\n"
        )
        assert expected_lines in caplog.text

    @mock.patch("logprep.ng.runner.Runner.instance")
    def test_main_calls_runner_stop_on_any_exception(self, mock_runner):
        mock_runner.run.side_effect = Exception
        config_path = "tests/testdata/config/config-ng.yml"
        result = self.cli_runner.invoke(cli, ["run", config_path])
        assert result.exit_code == 1
        mock_runner.stop.assert_called()

    def test_logprep_exits_on_invalid_configuration(self):
        with mock.patch("logprep.ng.util.configuration.Configuration._verify") as mock_verify:
            mock_verify.side_effect = InvalidConfigurationError("test error")
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value

    def test_logprep_exits_on_any_exception_during_verify(self):
        with mock.patch("logprep.ng.util.configuration.Configuration._verify") as mock_verify:
            mock_verify.side_effect = Exception
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    def test_logprep_exits_on_request_exception(self):
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_verify:
            mock_verify.side_effect = requests.RequestException("connection refused")
            config_path = "http://localhost/does-not-exists"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value

    @mock.patch("logging.Logger.info")
    def test_run_logprep_logs_log_level(self, mock_info):
        config = Configuration.from_sources(("tests/testdata/config/config-ng.yml",))
        assert config.logger.level == "INFO"
        with mock.patch("logprep.run_ng.Runner"):
            with pytest.raises(SystemExit):
                run_ng.run(("tests/testdata/config/config.yml",))
        for call in mock_info.call_args_list:
            if "Log level set to" in call[0][0]:
                break
        else:
            assert False, "Expected log message not found"
