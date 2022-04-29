# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule

pytest.importorskip("logprep.processor.normalizer")


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 1234 AND source_name: "test"',
        "hyperscan_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_list": {"pattern": "result"},
        },
        "description": "insert a description text",
    }


class TestHyperscanResolverRule:
    def test_rules_are_equal(self, specific_rule_definition):
        rule1 = HyperscanResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["hyperscan_resolver"],
        )

        rule2 = HyperscanResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["hyperscan_resolver"],
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = HyperscanResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["hyperscan_resolver"],
        )

        rule_diff_field_mapping = HyperscanResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["hyperscan_resolver"],
        )

        rule_diff_filter = HyperscanResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["hyperscan_resolver"],
        )

        rule_diff_field_mapping._field_mapping = {"different": "mapping"}
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_field_mapping
        assert rule != rule_diff_filter
        assert rule_diff_field_mapping != rule_diff_filter
