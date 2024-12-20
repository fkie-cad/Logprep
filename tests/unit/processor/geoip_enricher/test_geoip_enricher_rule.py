# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use

import pytest
from logprep.processor.geoip_enricher.rule import GeoipEnricherRule


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "message",
        "geoip_enricher": {"source_fields": ["source"], "target_field": "geoip"},
        "description": "",
    }


class TestListComparisonRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "message",
                    "geoip_enricher": {"source_fields": ["source"], "target_field": "geoip"},
                },
                True,
            ),
            (
                "Should be equal without target_field cause default is the same",
                {
                    "filter": "message",
                    "geoip_enricher": {"source_fields": ["source"]},
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "geoip_enricher": {"source_fields": ["source"], "target_field": "geoip"},
                },
                False,
            ),
            (
                "Should be not equal cause of other source_fields",
                {
                    "filter": "other_message",
                    "geoip_enricher": {
                        "source_fields": ["other_source"],
                        "target_field": "geoip",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other target_field",
                {
                    "filter": "other_message",
                    "geoip_enricher": {
                        "source_fields": ["source"],
                        "target_field": "other.geoip",
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = GeoipEnricherRule._create_from_dict(rule_definition)
        rule2 = GeoipEnricherRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
