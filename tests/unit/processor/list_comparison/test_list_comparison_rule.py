# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use

import pytest
from logprep.processor.list_comparison.rule import ListComparisonRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "user",
        "list_comparison": {
            "check_field": "user",
            "output_field": "user_results",
            "list_file_paths": ["../lists/user_list.txt"],
        },
        "description": "",
    }


class TestListComparisonRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "user",
                    "list_comparison": {
                        "check_field": "user",
                        "output_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_user",
                    "list_comparison": {
                        "check_field": "user",
                        "output_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other check_field",
                {
                    "filter": "user",
                    "list_comparison": {
                        "check_field": "other_user",
                        "output_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other output_field",
                {
                    "filter": "user",
                    "list_comparison": {
                        "check_field": "user",
                        "output_field": "other_user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other list_file_paths",
                {
                    "filter": "user",
                    "list_comparison": {
                        "check_field": "user",
                        "output_field": "other_user_results",
                        "list_file_paths": ["../lists/other_user_list.txt"],
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = ListComparisonRule._create_from_dict(specific_rule_definition)
        rule2 = ListComparisonRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    def test_compare_set_not_empty_for_valid_rule_def_after_init_list_comparison(
        self, specific_rule_definition
    ):
        rule = ListComparisonRule._create_from_dict(specific_rule_definition)

        rule.init_list_comparison("tests/testdata/unit/list_comparison/rules")

        assert rule.compare_sets is not None
        assert isinstance(rule.compare_sets, dict)
        assert len(rule.compare_sets.keys()) > 0

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": "other_message",
            "list_comparison": {
                "check_field": "user",
                "output_field": "other_user_results",
                "list_file_paths": ["../lists/other_user_list.txt"],
            },
            "description": "",
        }
        with pytest.deprecated_call() as warnings:
            ListComparisonRule._create_from_dict(rule_dict)
            assert len(warnings.list) == 2
            matches = [warning.message.args[0] for warning in warnings.list]
            assert "Use list_comparison.target_field instead" in matches[1]
            assert "Use list_comparison.source_fields instead" in matches[0]
