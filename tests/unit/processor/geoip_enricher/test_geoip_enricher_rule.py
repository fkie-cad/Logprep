# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use

import pytest
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

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": "other_message",
            "geoip_enricher": {
                "source_ip": "other_source",
                "output_field": "geoip",
            },
            "description": "",
        }
        with pytest.deprecated_call() as warnings:
            GeoipEnricherRule._create_from_dict(rule_dict)
            assert len(warnings.list) == 2
            matches = [warning.message.args[0] for warning in warnings.list]
            assert "Use geoip_enricher.target_field instead" in matches[1]
            assert "Use geoip_enricher.source_fields instead" in matches[0]
