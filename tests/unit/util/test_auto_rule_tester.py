# pylint: disable=missing-module-docstring
# pylint: disable=wrong-import-position
# pylint: disable=protected-access
import pytest

from yaml import safe_dump
from logprep.util.auto_rule_tester import AutoRuleTester


@pytest.fixture
def auto_rule_tester(tmp_path):
    config = {
        "process_count": 1,
        "timeout": 0.1,
        "pipeline": [
            {
                "normalizer_name": {
                    "type": "normalizer",
                    "specific_rules": [
                        "tests/testdata/unit/auto_rule_tester/normalizer/rules/specific"
                    ],
                    "generic_rules": [
                        "tests/testdata/unit/auto_rule_tester/normalizer/rules/generic"
                    ],
                    "regex_mapping": "tests/testdata/unit/auto_rule_tester/normalizer/"
                    "regex_mapping.yml",
                }
            }
        ],
    }
    config_path = str(tmp_path / "logprep_config.yml")
    with open(config_path, "w") as config_file:
        safe_dump(config, config_file)
    return AutoRuleTester(config_path)


class TestAutoRuleTester:
    def test_coverage_no_rule_files_raises_exception(self, auto_rule_tester):
        rules_pn = {
            "processor_name": {
                "rules": [],
                "type": "doesnt_matter",
            }
        }

        with pytest.raises(ZeroDivisionError):
            auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)

    def test_coverage_no_rule_files_have_tests(self, auto_rule_tester):
        rules_pn = {
            "processor_name": {
                "rules": [
                    {
                        "file": "rule",
                        "tests": [],
                    },
                    {
                        "file": "rule",
                        "tests": [],
                    },
                ],
                "type": "doesnt_matter",
            }
        }

        coverage = auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert coverage == 0

    def test_coverage_all_rule_files_have_tests(self, auto_rule_tester):
        rules_pn = {
            "processor_name": {
                "rules": [
                    {
                        "file": "rule",
                        "tests": [{"processed": {}, "raw": {}}],
                    },
                    {
                        "file": "rule",
                        "tests": [{"processed": {}, "raw": {}}],
                    },
                ],
                "type": "doesnt_matter",
            }
        }

        coverage = auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert coverage == 100

    def test_coverage_half_rule_files_have_tests(self, auto_rule_tester):
        rules_pn = {
            "processor_name": {
                "rules": [
                    {
                        "file": "rule",
                        "tests": [{"processed": {}, "raw": {}}],
                    },
                    {
                        "file": "rule",
                        "tests": [],
                    },
                ],
                "type": "doesnt_matter",
            }
        }

        coverage = auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert coverage == 50

    def test_does_not_run_if_no_rules_exist(self, auto_rule_tester):
        rules_pn = {
            "normalizer_name": {
                "rules": [],
                "type": "doesnt_matter",
            }
        }

        try:
            auto_rule_tester._run_if_any_rules_exist(rules_pn)
        except Exception as error:
            assert False, f"test_does_not_run_if_no_rules_exist has raised an exception: {error}"

    def test_does_run_if_rules_exist(self, auto_rule_tester):
        rules_pn = {
            "normalizer_name": {
                "rules": [
                    {
                        "file": "rule",
                        "tests": [],
                    },
                ],
                "type": "doesnt_matter",
            }
        }

        try:
            auto_rule_tester._run_if_any_rules_exist(rules_pn)
        except Exception as error:
            assert False, f"test_does_run_if_rules_exist has raised an exception: {error}"
