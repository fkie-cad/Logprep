# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
import sys
from pathlib import Path
from unittest import mock

import requests
import responses
from click.testing import CliRunner

from logprep._version import get_versions
from logprep.run_logprep import cli, Configuration
from logprep.util.configuration import InvalidConfigurationError


class TestRunLogprepCli:
    def setup_method(self):
        self.cli_runner = CliRunner()

    def teardown_method(self):
        Configuration._getters.clear()

    @mock.patch("logprep.run_logprep.Runner")
    def test_cli_run_starts_runner_with_config(self, mock_runner):
        runner_instance = mock.MagicMock()
        mock_runner.get_runner.return_value = runner_instance
        args = ["run", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        runner_instance.start.assert_called()
        config_file_path = "tests/testdata/config/config.yml"
        runner_instance.load_configuration.assert_called_with(config_file_path)

    @mock.patch("logprep.run_logprep.Runner")
    def test_cli_run_starts_runner_with_config(self, mock_runner):
        runner_instance = mock.MagicMock()
        mock_runner.get_runner.return_value = runner_instance
        args = ["run", "tests/testdata/config/config.yml", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        runner_instance.start.assert_called()
        config_file_path = "tests/testdata/config/config.yml"
        runner_instance.load_configuration.assert_called_with(config_file_path)

    @mock.patch("logprep.run_logprep.Runner")
    def test_cli_run_uses_getter_to_get_config(self, mock_runner):
        runner_instance = mock.MagicMock()
        mock_runner.get_runner.return_value = runner_instance
        args = ["run", "file://tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        runner_instance.start.assert_called()
        config_file_path = "file://tests/testdata/config/config.yml"
        runner_instance.load_configuration.assert_called_with(config_file_path)

    def test_exits_after_getter_error_for_not_existing_protocol(self):
        args = ["run", "almighty_protocol://tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 1
        assert "No getter for protocol 'almighty_protocol'" in result.output

    @mock.patch("logprep.util.configuration.Configuration.verify")
    def test_test_config_verifies_configuration_successfully(self, mock_verify):
        args = ["test", "config", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        mock_verify.assert_called()
        assert "The verification of the configuration was successful" in result.stdout

    @mock.patch("logprep.util.configuration.Configuration.verify")
    def test_test_config_verifies_configuration_unsuccessfully(self, mock_verify):
        mock_verify.side_effect = InvalidConfigurationError
        args = ["test", "config", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 1
        mock_verify.assert_called()
        assert "The verification of the configuration was successful" not in result.stdout

    @responses.activate
    def test_gets_config_from_https(self):
        pipeline_config = Path("tests/testdata/config/config.yml").read_text(encoding="utf8")
        responses.add(responses.GET, "https://does.not.exits/pipline.yml", pipeline_config)
        args = ["test", "config", "https://does.not.exits/pipline.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0

    def test_version_arg_prints_logprep_version(self):
        result = self.cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {get_versions()['version']}" in result.output
        assert f"configuration version:   no configuration found" in result.output

    def test_run_version_arg_prints_logprep_version_with_config_version(self):
        args = ["run", "--version", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {get_versions()['version']}" in result.output
        assert (
            "configuration version:   1, file://tests/testdata/config/config.yml" in result.output
        )

    def test_run_version_arg_prints_logprep_version_without_config_value(self):
        args = ["run", "--version", "tests/testdata/config/config2.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {get_versions()['version']}" in result.output
        assert (
            "configuration version:   unset, file://tests/testdata/config/config2.yml"
            in result.output
        )

    @responses.activate
    def test_run_version_arg_prints_with_http_config(self):
        config_path = "tests/testdata/config/config.yml"
        responses.add(
            responses.GET,
            f"http://localhost:32000/{config_path}",
            Path(config_path).read_text(encoding="utf8"),
        )
        args = ["run", "--version", f"http://localhost:32000/{config_path}"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {get_versions()['version']}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output

    @responses.activate
    def test_run_version_arg_prints_with_http_config_without_exposing_secret_data(self):
        config_path = "tests/testdata/config/config.yml"
        mock_env = {
            "LOGPREP_CONFIG_ATUH_USERNAME": "username",
            "LOGPREP_CONFIG_ATUH_PASSWORD": "password",
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
        assert f"logprep version:         {get_versions()['version']}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output
        assert "username" not in result.output
        assert "password" not in result.output

    def test_run_no_config_error_is_printed_if_no_config_was_arg_was_given(self):
        result = self.cli_runner.invoke(cli, ["run"])
        assert result.exit_code == 2
        assert "Usage: logprep run [OPTIONS] CONFIG\nTry 'logprep run --help' for help.\n\nError: Missing argument 'CONFIG'."

    def test_run_no_config_error_is_printed_if_given_config_file_does_not_exist(self, capsys):
        non_existing_config_file = "/tmp/does/not/exist.yml"
        result = self.cli_runner.invoke(cli, ["run", non_existing_config_file])
        assert result.exit_code == 1
        expected_lines = (
            f"One or more of the given config file(s) does not exist: "
            f"{non_existing_config_file}\n"
            f"Create the configuration or change the path. Use '--help' for more information."
        )
        assert expected_lines in result.output

    @mock.patch("logprep.runner.Runner.start")
    @mock.patch("logprep.runner.Runner.stop")
    def test_main_calls_runner_stop_on_any_exception(self, mock_stop, mock_start):
        mock_start.side_effect = Exception
        config_path = "tests/testdata/config/config.yml"
        result = self.cli_runner.invoke(cli, ["run", config_path])
        assert result.exit_code == 1
        mock_stop.assert_called()

    def test_logprep_exits_if_logger_can_not_be_created(self):
        with mock.patch("logprep.run_logprep.Configuration.get") as mock_create:
            mock_create.side_effect = BaseException
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    def test_logprep_exits_on_invalid_configuration(self):
        with mock.patch("logprep.util.configuration.Configuration.verify") as mock_verify:
            mock_verify.side_effect = InvalidConfigurationError
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    def test_logprep_exits_on_any_exception_during_verify(self):
        with mock.patch("logprep.util.configuration.Configuration.verify") as mock_verify:
            mock_verify.side_effect = Exception
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    def test_logprep_exits_on_request_exception(self):
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_verify:
            mock_verify.side_effect = requests.RequestException("connection refused")
            config_path = "http://localhost/does-not-exists"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    @mock.patch("logprep.util.rule_dry_runner.DryRunner.run")
    def test_test_dry_run_starts_dry_runner(self, mock_dry_runner):
        config_path = "tests/testdata/config/config.yml"
        events_path = "quickstart/exampledata/input_logdata/test_input.jsonl"
        result = self.cli_runner.invoke(cli, ["test", "dry-run", config_path, events_path])
        assert result.exit_code == 0
        mock_dry_runner.assert_called()

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_tester.AutoRuleTester.run")
    def test_test_rules_starts_auto_rule_tester(self, mock_tester):
        config_path = "tests/testdata/config/config.yml"
        result = self.cli_runner.invoke(cli, ["test", "unit", config_path])
        assert result.exit_code == 0
        mock_tester.assert_called()
        # the AutoRuleTester deactivates the logger which then has side effects on other tests
        # so the logger is being activated here again.
        logger = logging.getLogger()
        logger.disabled = False

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.RuleCorpusTester.run")
    def test_test_ruleset_starts_rule_corpus_tester(self, mock_tester):
        config_path = "tests/testdata/config/config.yml"
        test_data_path = "path/to/testset"
        result = self.cli_runner.invoke(cli, ["test", "integration", config_path, test_data_path])
        assert result.exit_code == 0
        mock_tester.assert_called()
