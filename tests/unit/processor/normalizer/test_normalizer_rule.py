from logprep.filter.lucene_filter import LuceneFilter

import pytest

pytest.importorskip("logprep.processor.normalizer")

from logprep.processor.normalizer.rule import NormalizerRule


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 1234 AND source_name: "test"',
        "normalize": {
            "winlog.event_data.param1": "normalized_test",
        },
        "description": "insert a description text",
    }


class TestNormalizerRule:
    def test_rules_are_equal(self, specific_rule_definition):
        rule1 = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )

        rule2 = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )

        rule_diff_substi = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )

        rule_diff_filter = NormalizerRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["normalize"],
        )

        rule_diff_substi._substitutions = ["I am different!"]
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_substi
        assert rule != rule_diff_filter
        assert rule_diff_substi != rule_diff_filter
