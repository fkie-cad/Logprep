# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import os.path
import sys
from unittest import mock

import pytest
from yaml import safe_load

from logprep import run_logprep
from logprep._version import get_versions
from logprep.run_logprep import DEFAULT_LOCATION_CONFIG


class TestRunLogprep:
    @mock.patch("logprep.run_logprep._run_logprep")
    def test_main_calls_run_logprep_with_quickstart_config(self, mock_run_logprep):
        """ensures the quickstart config is valid"""
        sys.argv = [
            "logprep",
            "--disable-logging",
            "quickstart/exampledata/config/pipeline.yml",
        ]
        run_logprep.main()
        mock_run_logprep.assert_called()

    @mock.patch("logprep.util.schema_and_rule_checker.SchemaAndRuleChecker.validate_rules")
    def test_main_calls_validates_rules(self, mock_validate_rules):
        """ensures rule validation is called"""
        sys.argv = [
            "logprep",
            "--disable-logging",
            "--validate-rules",
            "quickstart/exampledata/config/pipeline.yml",
        ]
        with pytest.raises(SystemExit):
            run_logprep.main()
        mock_validate_rules.assert_called()

    def test_quickstart_rules_are_valid(self):
        """ensures the quickstart rules are valid"""
        sys.argv = [
            "logprep",
            "--disable-logging",
            "--validate-rules",
            "quickstart/exampledata/config/pipeline.yml",
        ]
        with pytest.raises(SystemExit) as e_info:
            run_logprep.main()
        assert e_info.value.code == 0

    def test_version_arg_prints_logprep_version_without_config_argument(self, capsys):
        sys.argv = ["logprep", "--version"]
        with pytest.raises(SystemExit):
            run_logprep.main()
        captured = capsys.readouterr()
        logprep_line, config_line = captured.out.strip().split("\n")
        assert logprep_line == f"logprep version: \t\t {get_versions()['version']}"
        assert (
            config_line
            == f"configuration version: \t no configuration found in '{DEFAULT_LOCATION_CONFIG}'"
        )

    def test_version_arg_prints_also_config_version_if_version_key_is_found(self, capsys):
        config_path = "quickstart/exampledata/config/pipeline.yml"
        sys.argv = ["logprep", "--version", config_path]
        with pytest.raises(SystemExit):
            run_logprep.main()
        captured = capsys.readouterr()
        lines = captured.out.strip()
        with open(config_path, "r", encoding="utf-8") as file:
            configuration = safe_load(file)
        expected_lines = (
            f"logprep version: \t\t {get_versions()['version']}\n"
            f"configuration version: \t {configuration['version']}, {os.path.abspath(config_path)}"
        )
        assert lines == expected_lines

    def test_no_config_error_is_printed_if_no_config_was_arg_was_given(self, capsys):
        sys.argv = ["logprep"]
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
        sys.argv = ["logprep", non_existing_config_file]
        with pytest.raises(SystemExit):
            run_logprep.main()
        captured = capsys.readouterr()
        error_lines = captured.err.strip()
        expected_lines = (
            f"The given config file does not exist: {non_existing_config_file}\nCreate the "
            f"configuration or change the path. Use '--help' for more information."
        )
        assert error_lines == expected_lines
