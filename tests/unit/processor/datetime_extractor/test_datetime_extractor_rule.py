# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable
import pytest

from logprep.processor.datetime_extractor.rule import DatetimeExtractorRule


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "field.a",
        "datetime_extractor": {"source_fields": ["field.a"], "target_field": "datetime"},
        "description": "",
    }


class TestDatetimeExtractorRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Equal because the same",
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": ["field.a"],
                        "target_field": "datetime",
                    },
                    "description": "",
                },
                True,
            ),
            (
                "Not equal because of different filter",
                {
                    "filter": "field.b",
                    "datetime_extractor": {
                        "source_fields": ["field.a"],
                        "target_field": "datetime",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because of different datetime_field",
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": ["field.b"],
                        "target_field": "datetime",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because different destination",
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": ["field.a"],
                        "target_field": "other",
                    },
                    "description": "",
                },
                False,
            ),
            (
                "Not equal because different destination and datetime_field",
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": ["field.b"],
                        "target_field": "other",
                    },
                    "description": "",
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule_1 = DatetimeExtractorRule._create_from_dict(rule_definition)
        rule_2 = DatetimeExtractorRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "field.a",
                    "datetime_extractor": {
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
                    "datetime_extractor": {
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
                    "datetime_extractor": {
                        "source_fields": ["field.b"],
                    },
                    "description": "",
                },
                TypeError,
                "missing 1 required keyword-only argument: 'target_field'",
            ),
            (
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "target_field": "other",
                    },
                    "description": "",
                },
                TypeError,
                "missing 1 required keyword-only argument: 'source_fields'",
            ),
            (
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": [["field.b"]],
                        "target_field": "other",
                    },
                    "description": "",
                },
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "source_fields": ["field.b"],
                        "target_field": 111,
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
                _ = DatetimeExtractorRule._create_from_dict(rule_definition)
        else:
            extractor_rule = DatetimeExtractorRule._create_from_dict(rule_definition)
            assert isinstance(extractor_rule, DatetimeExtractorRule)

    def test_rule_is_hashable(self, rule_definition):
        rule = DatetimeExtractorRule._create_from_dict(rule_definition)
        assert isinstance(rule, Hashable)
