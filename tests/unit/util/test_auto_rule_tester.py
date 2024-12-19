# pylint: disable=protected-access
# pylint: disable=broad-exception-caught
# pylint: disable=missing-function-docstring)
import logging
import re
from unittest import mock
import pytest

from logprep.util.auto_rule_tester.auto_rule_tester import AutoRuleTester
from logprep.util.configuration import Configuration

LOGGER = logging.getLogger()


@pytest.fixture(name="auto_rule_tester")
def fixture_auto_rule_tester():
    config_path = "tests/testdata/config/config-auto-tests.yml"
    Configuration.from_source(config_path)._verify()
    return AutoRuleTester(config_path)


class TestAutoRuleTester:

    def test_get_rule_dict_valid_file(self, auto_rule_tester):
        processor_name = "dummy"
        rules_pn = {"dummy": {"type": "dummy", "rules": []}}
        file = "rule.yml"
        root = "tests/testdata/auto_tests/dummy"

        auto_rule_tester._get_rule_dict(file, root, processor_name, rules_pn)

        # raw literal
        expected_rule_dict = [
            {
                "rules": [
                    {
                        "filter": 'winlog.event_data.param2: "pause"',
                        "labeler": {"label": {"action": ["terminate"]}},
                        "description": "...",
                    },
                    {
                        "filter": 'winlog.event_data.param2: "dada"',
                        "labeler": {"label": {"action": ["terminate"]}},
                        "description": "...",
                    },
                ],
                "tests": [
                    {
                        "target_rule_idx": 0,
                        "raw": {"winlog": {"event_data": {"param2": "ooo"}}},
                        "processed": {
                            "label": {"action": ["terminate"]},
                            "winlog": {"event_data": {"param2": "pause"}},
                        },
                    },
                    {
                        "raw": {"winlog": {"event_data": {"param2": "pause"}}},
                        "processed": {
                            "label": {"action": ["terminate"]},
                            "winlog": {"event_data": {"param2": "pause"}},
                        },
                    },
                    {
                        "target_rule_idx": 1,
                        "raw": {"winlog": {"event_data": {"param2": "dada"}}},
                        "processed": {
                            "label": {"action": ["terminate"]},
                            "winlog": {"event_data": {"param2": "dada"}},
                        },
                    },
                ],
                "file": "tests/testdata/auto_tests/dummy/rule.yml",
            }
        ]

        assert rules_pn["dummy"]["rules"] == expected_rule_dict

    def test_get_rule_dict_target_rule_idx_not_found(self, auto_rule_tester):
        processor_name = "dummy"
        rules_pn = {"dummy": {"type": "dummy", "rules": []}}
        file = "rule.yml"
        root = "tests/testdata/auto_tests/dummy"

        auto_rule_tester._get_rule_dict(file, root, processor_name, rules_pn)

        def remove_dict_with_target_rule_idx(list_of_dicts):
            for idx, d in enumerate(list_of_dicts):
                if "target_rule_idx" in d:
                    del list_of_dicts[idx]
                    break

        remove_dict_with_target_rule_idx(rules_pn["dummy"]["rules"])

        with pytest.raises(KeyError):
            for test in rules_pn["dummy"]["rules"]:
                for t in test["tests"]:
                    t["target_rule_idx"]

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

        auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert auto_rule_tester._result["Rule Test Coverage"] == 0

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

        auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert auto_rule_tester._result["Rule Test Coverage"] == 100

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

        auto_rule_tester._check_which_rule_files_miss_tests(rules_pn)
        assert auto_rule_tester._result["Rule Test Coverage"] == 50

    def test_does_not_run_if_no_rules_exist(self, auto_rule_tester, capsys):
        rules_pn = {
            "dissector_name": {
                "rules": [],
                "type": "doesnt_matter",
            }
        }

        try:
            auto_rule_tester._run_if_any_rules_exist(rules_pn)
            captured = capsys.readouterr()
            assert "There are no rules within any of the rules directories!" in captured.out
        except Exception as error:
            assert False, f"test_does_not_run_if_no_rules_exist has raised an exception: {error}"

    def test_does_run_if_rules_exist(self, auto_rule_tester):
        auto_rule_tester._config_yml["pipeline"] = [
            {
                "dissector": {
                    "type": "dissector",
                    "rules": ["tests/testdata/auto_tests/dissector/rules"],
                }
            }
        ]
        rules_pn = {
            "dissector": {
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
    def test_pseudonymizer_specific_setup_called_on_load_rules(
        self, mock_replace_regex_keywords_by_regex_expression, auto_rule_tester
    ):
        pseudonymizer_cfg = {
            "type": "pseudonymizer",
            "outputs": [{"jsonl": "pseudonyms"}],
            "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
            "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
            "hash_salt": "a_secret_tasty_ingredient",
            "rules": ["tests/testdata/unit/pseudonymizer/rules"],
            "regex_mapping": "tests/testdata/unit/pseudonymizer/regex_mapping.yml",
            "max_cached_pseudonyms": 1000000,
        }
        mock_replace_regex_keywords_by_regex_expression.assert_not_called()
        processor = auto_rule_tester._get_processor_instance("pseudonymizer", pseudonymizer_cfg)
        auto_rule_tester._reset(processor)  # Called every time by auto tester before adding rules
        auto_rule_tester._load_rules(processor)
        assert mock_replace_regex_keywords_by_regex_expression.call_count == 1

    @mock.patch("logprep.processor.list_comparison.processor.ListComparison.setup")
    def test_list_comparison_specific_setup_called_on_load_rules(
        self, mock_setup, auto_rule_tester
    ):
        list_comparison_cfg = {
            "type": "list_comparison",
            "rules": ["tests/testdata/unit/list_comparison/rules"],
            "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
        }
        mock_setup.assert_not_called()
        processor = auto_rule_tester._get_processor_instance("list_comparison", list_comparison_cfg)
        auto_rule_tester._reset(
            processor
        )  # Called every time by auto tester before adding rules instead
        auto_rule_tester._load_rules(processor)
        mock_setup.assert_called_once()

    def test_full_auto_rule_test_run(self, auto_rule_tester, capsys):
        with pytest.raises(SystemExit):
            auto_rule_tester.run()
        expected_rules_with_tests = [
            "with tests",
            "tests/testdata/auto_tests/labeler/rules/auto_test_labeling_match.json",
            "tests/testdata/auto_tests/labeler/rules/auto_test_labeling_mismatch.json",
            "tests/testdata/auto_tests/dissector/rules/auto_test_match.json",
            "tests/testdata/auto_tests/dissector/rules/auto_test_mismatch.json",
            "tests/testdata/auto_tests/dropper/rules/drop_field_1.json",
            "tests/testdata/auto_tests/dropper/rules/drop_field_2.json",
            "tests/testdata/auto_tests/pre_detector/rules/auto_test_pre_detector_match.json",
            "tests/testdata/auto_tests/pre_detector/rules/auto_test_pre_detector_mismatch.json",
            "tests/testdata/auto_tests/pseudonymizer/rules/auto_test_pseudonymizer_mismatch.json",
            "tests/testdata/auto_tests/pseudonymizer/rules/auto_test_pseudonymizer_match.json",
            "tests/testdata/auto_tests/template_replacer/rules/template_replacer_1.json",
            "tests/testdata/auto_tests/template_replacer/rules/template_replacer_2.json",
        ]
        expected_rules_without_tests = [
            "without tests",
            "tests/testdata/auto_tests/labeler/rules/auto_test_labeling_no_test_.json",
            "tests/testdata/auto_tests/dissector/rules/auto_test_no_test_.json",
            "tests/testdata/auto_tests/pre_detector/rules/auto_test_pre_detector_no_test_.json",
            "tests/testdata/auto_tests/pseudonymizer/rules/auto_test_pseudonymizer_no_test_.json",
        ]

        expected_overall_results = [
            "+ Successful Tests: 32",
            "- Failed Tests: 6",
            "~ Warning: 2",
            "Rule Test Coverage: 72.72727272727273",
            "Total Tests: 38",
        ]
        captured = capsys.readouterr()

        float_pattern = r"(\d+(?:\.\d+)?).*"
        for expected_result in expected_overall_results:
            split_sample = expected_result.rsplit(" ", maxsplit=1)
            if len(split_sample) == 2:
                expected = re.search(float_pattern, split_sample[1]).group(1)
                pattern = f".*?{re.escape(split_sample[0])} {float_pattern}.*"
                match = re.search(pattern, captured.out)
                if match:
                    assert match.group(1) == expected, f'Expected: "{expected_result}"'

        expected_sample_lines = (
            expected_rules_with_tests + expected_rules_without_tests + expected_overall_results
        )
        for line in expected_sample_lines:
            assert line in captured.out

        assert "inverse check, this text should not be in captured out" not in captured.out
