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
    def test_rules_are_equal(self, specific_rule_definition):
        rule1 = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        rule2 = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        rule_diff_check_field = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        rule_diff_filter = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        rule_diff_check_field._check_field = ["diff_field"]
        rule_diff_filter._filter = ["diff_user"]

        assert rule != rule_diff_check_field
        assert rule != rule_diff_filter
        assert rule_diff_check_field != rule_diff_filter

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
