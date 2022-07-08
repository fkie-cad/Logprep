# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=broad-except
import logging
from unittest import mock

import pytest

from yaml import safe_dump
from logprep.util.auto_rule_tester import AutoRuleTester

LOGGER = logging.getLogger()


@pytest.fixture(name="auto_rule_tester")
def fixture_auto_rule_tester(tmp_path):
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
    with open(config_path, "w", encoding="utf-8") as config_file:
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

    @mock.patch(
        "logprep.processor.pseudonymizer.processor.Pseudonymizer."
        "_replace_regex_keywords_by_regex_expression"
    )
    def test_pseudonymizer_specific_setup_called_on_add_rules_from_directory(
        self, mock_replace_regex_keywords_by_regex_expression, auto_rule_tester
    ):
        pseudonymizer_cfg = {
            "type": "pseudonymizer",
            "pseudonyms_topic": "pseudonyms",
            "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
            "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/pseudonymizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/pseudonymizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
            "max_cached_pseudonyms": 1000000,
            "max_caching_days": 1,
        }
        mock_replace_regex_keywords_by_regex_expression.assert_not_called()
        processor = auto_rule_tester._get_processor_instance(
            "pseudonymizer", pseudonymizer_cfg, LOGGER
        )
        auto_rule_tester._reset_trees(
            processor
        )  # Called every time by auto tester before adding rules
        mock_replace_regex_keywords_by_regex_expression.assert_called_once()
        auto_rule_tester._add_rules_from_directory(processor, "specific_rules")
        assert mock_replace_regex_keywords_by_regex_expression.call_count == 2

    @mock.patch(
        "logprep.processor.list_comparison.processor.ListComparison._init_rules_list_comparison"
    )
    def test_list_comparison_specific_setup_called_on_add_rules_from_directory(
        self, mock_init_rules_list_comparison, auto_rule_tester
    ):
        list_comparison_cfg = {
            "type": "list_comparison",
            "specific_rules": ["tests/testdata/unit/list_comparison/rules/specific"],
            "generic_rules": ["tests/testdata/unit/list_comparison/rules/generic"],
            "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
        }
        mock_init_rules_list_comparison.assert_not_called()
        processor = auto_rule_tester._get_processor_instance(
            "list_comparison", list_comparison_cfg, LOGGER
        )
        auto_rule_tester._reset_trees(
            processor
        )  # Called every time by auto tester before adding rules instead
        mock_init_rules_list_comparison.assert_called_once()
        auto_rule_tester._add_rules_from_directory(processor, "specific_rules")
        assert mock_init_rules_list_comparison.call_count == 2
