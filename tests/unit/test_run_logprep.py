# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import sys
from unittest import mock

import pytest
from logprep import run_logprep


class TestRunLogprep:
    @mock.patch("logprep.run_logprep._run_logprep")
    def test_main_calls_run_logprep_with_quickstart_config(self, mock_run_logprep):
        """ensures the quickstart config is valid"""
        sys.argv = ["logprep", "--disable-logging", "quickstart/exampledata/config/pipeline.yml"]
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
