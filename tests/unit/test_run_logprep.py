# pylint: disable=missing-docstring
# pylint: disable=protected-access
import sys
from pathlib import Path
from unittest import mock

import pytest
import responses
import requests
from yaml import safe_load

from logprep import run_logprep
from logprep._version import get_versions
from logprep.run_logprep import DEFAULT_LOCATION_CONFIG
from logprep.util.configuration import InvalidConfigurationError
from logprep.util.getter import GetterNotFoundError


class TestRunLogprep:
    @mock.patch("logprep.run_logprep._run_logprep")
    def test_main_calls_run_logprep_with_quickstart_config(self, mock_run_logprep):
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "quickstart/exampledata/config/pipeline.yml",
            ],
        ):
            run_logprep.main()
        mock_run_logprep.assert_called()

    @mock.patch("logprep.util.schema_and_rule_checker.SchemaAndRuleChecker.validate_rules")
    def test_main_calls_validates_rules(self, mock_validate_rules):
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "--validate-rules",
                "quickstart/exampledata/config/pipeline.yml",
            ],
        ):
            with pytest.raises(SystemExit):
                run_logprep.main()
        mock_validate_rules.assert_called()

    def test_uses_getter_to_get_config(self):
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "--validate-rules",
                "file://quickstart/exampledata/config/pipeline.yml",
            ],
        ):
            with pytest.raises(SystemExit, match="0"):
                run_logprep.main()

    def test_raises_getter_error_for_not_existing_protocol(self):
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "--validate-rules",
                "almighty_protocol://quickstart/exampledata/config/pipeline.yml",
            ],
        ):
            with pytest.raises(
                GetterNotFoundError, match="No getter for protocol 'almighty_protocol'"
            ):
                run_logprep.main()

    @responses.activate
    def test_gets_config_from_https(self):
        pipeline_config = Path("quickstart/exampledata/config/pipeline.yml").read_text(
            encoding="utf8"
        )
        responses.add(responses.GET, "https://does.not.exits/pipline.yml", pipeline_config)
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "--validate-rules",
                "https://does.not.exits/pipline.yml",
            ],
        ):
            with pytest.raises(SystemExit, match="0"):
                run_logprep.main()

    def test_quickstart_rules_are_valid(self):
        """ensures the quickstart rules are valid"""
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--disable-logging",
                "--validate-rules",
                "quickstart/exampledata/config/pipeline.yml",
            ],
        ):
            with pytest.raises(SystemExit) as e_info:
                run_logprep.main()
        assert e_info.value.code == 0

    def test_version_arg_prints_logprep_version_without_config_argument(self, capsys):
        with mock.patch("sys.argv", ["logprep", "--version"]):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        python_line, logprep_line, config_line = captured.out.strip().split("\n")
        assert python_line == f"python version:          {sys.version.split()[0]}"
        assert logprep_line == f"logprep version:         {get_versions()['version']}"
        assert (
            config_line
            == f"configuration version:   no configuration found in '{DEFAULT_LOCATION_CONFIG}'"
        )

    def test_version_arg_prints_also_config_version_if_version_key_is_found(self, capsys):
        config_path = "quickstart/exampledata/config/pipeline.yml"
        with mock.patch("sys.argv", ["logprep", "--version", config_path]):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        lines = captured.out.strip()
        with open(config_path, "r", encoding="utf-8") as file:
            configuration = safe_load(file)
        expected_lines = (
            f"python version:          {sys.version.split()[0]}\n"
            f"logprep version:         {get_versions()['version']}\n"
            f"configuration version:   {configuration['version']}, file://{config_path}"
        )
        assert lines == expected_lines

    @responses.activate
    def test_version_arg_prints_with_http_config(self, capsys):
        config_path = "quickstart/exampledata/config/pipeline.yml"
        responses.add(
            responses.GET,
            "http://localhost:32000/quickstart/exampledata/config/pipeline.yml",
            Path(config_path).read_text(encoding="utf8"),
        )
        with mock.patch(
            "sys.argv", ["logprep", "--version", f"http://localhost:32000/{config_path}"]
        ):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        lines = captured.out.strip()
        with open(config_path, "r", encoding="utf-8") as file:
            configuration = safe_load(file)
        expected_lines = (
            f"python version:          {sys.version.split()[0]}\n"
            f"logprep version:         {get_versions()['version']}\n"
            f"configuration version:   {configuration['version']}, http://localhost:32000/{config_path}"
        )
        assert lines == expected_lines

    @responses.activate
    def test_version_arg_prints_with_http_config_without_exposing_secret_data(self, capsys):
        config_path = "quickstart/exampledata/config/pipeline.yml"
        responses.add(
            responses.GET,
            "http://localhost:32000/quickstart/exampledata/config/pipeline.yml",
            Path(config_path).read_text(encoding="utf8"),
        )
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "--version",
                f"http://username:password@localhost:32000/{config_path}",
            ],
        ):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        lines = captured.out.strip()
        with open(config_path, "r", encoding="utf-8") as file:
            configuration = safe_load(file)
        expected_lines = (
            f"python version:          {sys.version.split()[0]}\n"
            f"logprep version:         {get_versions()['version']}\n"
            f"configuration version:   {configuration['version']}, http://localhost:32000/{config_path}"
        )
        assert lines == expected_lines

    def test_no_config_error_is_printed_if_no_config_was_arg_was_given(self, capsys):
        with mock.patch("sys.argv", ["logprep"]):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        error_lines = captured.err.strip()
        expected_lines = (
            f"The given config file does not exist: {DEFAULT_LOCATION_CONFIG}\nCreate the "
            f"configuration or change the path. Use '--help' for more information."
        )
        assert error_lines == expected_lines

    def test_no_config_error_is_printed_if_given_config_file_does_not_exist(self, capsys):
        non_existing_config_file = "/tmp/does/not/exist.yml"
        with mock.patch("sys.argv", ["logprep", non_existing_config_file]):
            with pytest.raises(SystemExit):
                run_logprep.main()
        captured = capsys.readouterr()
        error_lines = captured.err.strip()
        expected_lines = (
            f"The given config file does not exist: {non_existing_config_file}\nCreate the "
            f"configuration or change the path. Use '--help' for more information."
        )
        assert error_lines == expected_lines

    @mock.patch("logprep.runner.Runner.load_configuration")
    @mock.patch("logprep.runner.Runner.start")
    def test_main_loads_configuration_and_starts_runner(self, mock_start, mock_load):
        config_path = "quickstart/exampledata/config/pipeline.yml"
        with mock.patch("sys.argv", ["logprep", config_path]):
            run_logprep.main()
        mock_load.assert_called_with(config_path)
        mock_start.assert_called()

    @mock.patch("logprep.runner.Runner.start")
    @mock.patch("logprep.runner.Runner.stop")
    def test_main_calls_runner_stop_on_any_exception(self, mock_stop, mock_start):
        mock_start.side_effect = Exception
        config_path = "quickstart/exampledata/config/pipeline.yml"
        with mock.patch("sys.argv", ["logprep", config_path]):
            run_logprep.main()
        mock_stop.assert_called()

    def test_logprep_exits_if_logger_can_not_be_created(self):
        with mock.patch("logprep.run_logprep.AggregatingLogger.create") as mock_create:
            mock_create.side_effect = BaseException
            config_path = "quickstart/exampledata/config/pipeline.yml"
            with mock.patch("sys.argv", ["logprep", config_path]):
                with pytest.raises(SystemExit):
                    run_logprep.main()

    def test_logprep_exits_on_invalid_configuration(self):
        with mock.patch("logprep.util.configuration.Configuration.verify") as mock_verify:
            mock_verify.side_effect = InvalidConfigurationError
            config_path = "quickstart/exampledata/config/pipeline.yml"
            with mock.patch("sys.argv", ["logprep", config_path]):
                with pytest.raises(SystemExit):
                    run_logprep.main()

    def test_logprep_exits_on_any_exception_during_verify(self):
        with mock.patch("logprep.util.configuration.Configuration.verify") as mock_verify:
            mock_verify.side_effect = Exception
            config_path = "quickstart/exampledata/config/pipeline.yml"
            with mock.patch("sys.argv", ["logprep", config_path]):
                with pytest.raises(SystemExit):
                    run_logprep.main()

    def test_logprep_exits_on_request_exception(self):
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_verify:
            mock_verify.side_effect = requests.RequestException("connection refused")
            with mock.patch("sys.argv", ["logprep", "http://localhost/does-not-exists"]):
                with pytest.raises(SystemExit):
                    run_logprep.main()
