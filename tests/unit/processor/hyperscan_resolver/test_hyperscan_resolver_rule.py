# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule

pytest.importorskip("logprep.processor.normalizer")


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
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
        rule1 = HyperscanResolverRule._create_from_dict(
            specific_rule_definition,
        )

        rule2 = HyperscanResolverRule._create_from_dict(
            specific_rule_definition,
        )

        assert rule1 == rule2

    def test_rules_are_not_equal(self, specific_rule_definition):
        rule = HyperscanResolverRule._create_from_dict(
            specific_rule_definition,
        )

        rule_diff_field_mapping = HyperscanResolverRule._create_from_dict(
            specific_rule_definition,
        )

        rule_diff_filter = HyperscanResolverRule._create_from_dict(
            specific_rule_definition,
        )

        rule_diff_field_mapping._field_mapping = {"different": "mapping"}
        rule_diff_filter._filter = ["I am different!"]

        assert rule != rule_diff_field_mapping
        assert rule != rule_diff_filter
        assert rule_diff_field_mapping != rule_diff_filter

    def test_replace_pattern_with_parenthesis_after_closing_parenthesis_not_included_in_replacement(
        self,
    ):
        replaced_pattern = HyperscanResolverRule._replace_pattern(
            "123abc456",
            r"\d*(?P<mapping>[a-z]+)c)\d*",
        )

        assert replaced_pattern == "\\d*123abc456c)\\d*"

    def test_replace_pattern_with_escaped_parenthesis_is_included_in_replacement(
        self,
    ):
        replaced_pattern = HyperscanResolverRule._replace_pattern(
            r"123ab\)c123", r"\d*(?P<mapping>[a-z]+\)c)\d*"
        )

        assert replaced_pattern == "\\d*123ab\\\\\\)c123\\d*"
