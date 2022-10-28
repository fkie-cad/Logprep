# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable
import warnings
import pytest

from logprep.processor.datetime_extractor.rule import DatetimeExtractorRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "field.a",
        "datetime_extractor": {"datetime_field": "field.a", "destination_field": "datetime"},
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
                        "datetime_field": "field.a",
                        "destination_field": "datetime",
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
                        "datetime_field": "field.a",
                        "destination_field": "datetime",
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
                        "datetime_field": "field.b",
                        "destination_field": "datetime",
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
                        "datetime_field": "field.a",
                        "destination_field": "other",
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
                        "datetime_field": "field.b",
                        "destination_field": "other",
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
        rule_1 = DatetimeExtractorRule._create_from_dict(specific_rule_definition)
        rule_2 = DatetimeExtractorRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "field.a",
                    "datetime_extractor": {
                        "datetime_field": "field.b",
                        "destination_field": "other",
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
                        "datetime_field": "field.b",
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
                        "destination_field": "other",
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
                        "datetime_field": ["field.b"],
                        "destination_field": "other",
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
                        "datetime_field": "field.b",
                        "destination_field": 111,
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

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = DatetimeExtractorRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": "field.a",
            "datetime_extractor": {
                "datetime_field": "field.b",
                "destination_field": "other",
            },
            "description": "",
        }
        with pytest.deprecated_call() as w:
            DatetimeExtractorRule._create_from_dict(rule_dict)
            assert len(w.list) == 2
            matches = [warning.message.args[0] for warning in w.list]
            assert "Use datetime_extractor.target_field instead" in matches[1]
            assert "Use datetime_extractor.source_fields instead" in matches[0]
