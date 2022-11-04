# pylint: disable=missing-docstring
# pylint: disable=protected-access

from typing import Hashable
import pytest
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "field.a",
        "domain_label_extractor": {
            "target_field": "field.a",
            "output_field": "datetime",
        },
        "description": "",
    }


class TestDomainLabelExtractorRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Equal because the same",
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.a",
                        "output_field": "datetime",
                    },
                    "description": "",
                },
                True,
            ),
            (
                "Not equal because of different filter",
                {
                    "filter": "field.b",
                    "domain_label_extractor": {
                        "target_field": "field.a",
                        "output_field": "datetime",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because of different target_field",
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.b",
                        "output_field": "datetime",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because different destination",
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.a",
                        "output_field": "other",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because different destination and target_field",
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.b",
                        "output_field": "other",
                    },
                    "description": "",
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule_1 = DomainLabelExtractorRule._create_from_dict(specific_rule_definition)
        rule_2 = DomainLabelExtractorRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.b",
                        "output_field": "other",
                    },
                    "description": "",
                },
                None,
                None,
            ),
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "source_fields": ["field.b"],
                        "target_field": "other",
                    },
                    "description": "",
                },
                None,
                None,
            ),
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.b",
                    },
                    "description": "",
                },
                TypeError,
                "missing 1 required keyword-only argument: 'source_fields'",
            ),
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "output_field": "other",
                    },
                    "description": "",
                },
                TypeError,
                "missing 1 required keyword-only argument: 'source_fields'",
            ),
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": ["field.b"],
                        "output_field": "other",
                    },
                    "description": "",
                },
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {
                    "filter": "field.a",
                    "domain_label_extractor": {
                        "target_field": "field.b",
                        "output_field": 111,
                    },
                    "description": "",
                },
                TypeError,
                "must be <class 'str'>",
            ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, raised, message):
        if raised:
            with pytest.raises(raised, match=message):
                _ = DomainLabelExtractorRule._create_from_dict(rule_definition)
        else:
            extractor_rule = DomainLabelExtractorRule._create_from_dict(rule_definition)
            assert isinstance(extractor_rule, DomainLabelExtractorRule)

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = DomainLabelExtractorRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)
