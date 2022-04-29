# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.generic_resolver.rule import GenericResolverRule

pytest.importorskip("logprep.processor.normalizer")


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": 'winlog.event_id: 1234 AND source_name: "test"',
        "generic_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_list": {"pattern": "result"},
        },
        "description": "insert a description text",
    }


class TestGenericResolverRule:
    def test_rules_are_equal(self, specific_rule_definition):
        rule1 = GenericResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["generic_resolver"],
        )

        rule2 = GenericResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["generic_resolver"],
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = GenericResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["generic_resolver"],
        )

        rule_diff_field_mapping = GenericResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["generic_resolver"],
        )

        rule_diff_filter = GenericResolverRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["generic_resolver"],
        )

        rule_diff_field_mapping._field_mapping = {"different": "mapping"}
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_field_mapping
        assert rule != rule_diff_filter
        assert rule_diff_field_mapping != rule_diff_filter
