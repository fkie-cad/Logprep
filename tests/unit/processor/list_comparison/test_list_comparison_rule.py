from logprep.filter.lucene_filter import LuceneFilter

import pytest

pytest.importorskip("logprep.processor.list_comparison")

from unittest import mock
from logprep.processor.list_comparison.rule import ListComparisonRule


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": "user",
        "list_comparison": {
            "check_field": "user",
            "output_field": "user_results",
            "list_file_paths": [
                "tests/testdata/unit/list_comparison/lists/user_list.txt"
            ],
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

    def test_compare_set_not_empty_for_valid_rule_def(self, specific_rule_definition):
        self.rule = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )

        assert self.rule._compare_sets is not None
        assert isinstance(self.rule._compare_sets, dict)
        assert len(self.rule._compare_sets.keys()) > 0

    @mock.patch(
        "logprep.processor.list_comparison.rule.ListComparisonRule.init_list_comparison"
    )
    def test_init_compare_sets_is_called(self, mock_method, specific_rule_definition):
        rule = ListComparisonRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["list_comparison"],
        )
        mock_method.assert_called()
