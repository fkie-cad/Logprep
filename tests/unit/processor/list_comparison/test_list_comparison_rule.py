# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from unittest import mock

import pytest
from logprep.filter.lucene_filter import LuceneFilter
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
        rule1 = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )
        rule2 = ListComparisonRule(
            LuceneFilter.create(other_rule_definition["filter"]),
            other_rule_definition["list_comparison"],
        )
        assert (rule1 == rule2) == is_equal, testcase

    def test_compare_set_not_empty_for_valid_rule_def_after_init_list_comparison(
        self, specific_rule_definition
    ):
        rule = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        rule.init_list_comparison("tests/testdata/unit/list_comparison/rules")

        assert rule._compare_sets is not None
        assert isinstance(rule._compare_sets, dict)
        assert len(rule._compare_sets.keys()) > 0
