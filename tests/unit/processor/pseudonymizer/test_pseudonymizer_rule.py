from logprep.filter.lucene_filter import LuceneFilter

import pytest

pytest.importorskip("logprep.processor.pseudonymizer")

from logprep.processor.pseudonymizer.rule import PseudonymizerRule


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 123 AND source_name: "Test123"',
        "pseudonymize": {
            "winlog.event_data.param1": "RE_WHOLE_FIELD",
            "winlog.event_data.param2": "RE_WHOLE_FIELD",
        },
        "description": "insert a description text",
    }


class TestPseudonomyzerRule:
    def test_rules_are_equal(self, specific_rule_definition):
        rule1 = PseudonymizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pseudonymize"],
        )

        rule2 = PseudonymizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pseudonymize"],
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = PseudonymizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pseudonymize"],
        )

        rule_diff_pseudo = PseudonymizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pseudonymize"],
        )

        rule_diff_filter = PseudonymizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pseudonymize"],
        )

        rule_diff_pseudo._pseudonyms = ["I am different!"]
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_pseudo
        assert rule != rule_diff_filter
        assert rule_diff_pseudo != rule_diff_filter
