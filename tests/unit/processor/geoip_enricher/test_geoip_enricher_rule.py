# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from unittest import mock

import pytest
from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.geoip_enricher.rule import GeoipEnricherRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "message",
        "geoip_enricher": {"source_ip": "source", "output_field": "geoip"},
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
                    "geoip_enricher": {"source_ip": "source", "output_field": "geoip"},
                },
                True,
            ),
            (
                "Should be equal without output_field cause default is the same",
                {
                    "filter": "message",
                    "geoip_enricher": {"source_ip": "source"},
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "geoip_enricher": {"source_ip": "source", "output_field": "geoip"},
                },
                False,
            ),
            (
                "Should be not equal cause of other source_ip",
                {
                    "filter": "other_message",
                    "geoip_enricher": {
                        "source_ip": "other_source",
                        "output_field": "geoip",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other output_field",
                {
                    "filter": "other_message",
                    "geoip_enricher": {
                        "source_ip": "source",
                        "output_field": "other.geoip",
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = GeoipEnricherRule._create_from_dict(specific_rule_definition)
        rule2 = GeoipEnricherRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
