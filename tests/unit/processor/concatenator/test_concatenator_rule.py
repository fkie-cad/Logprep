# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable

import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.concatenator.rule import ConcatenatorRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "field.a",
        "concatenator": {
            "source_fields": ["field.a", "field.b", "other_field.c"],
            "target_field": "target_field",
            "separator": "-",
            "overwrite_target": False,
            "delete_source_fields": False,
        },
        "description": "",
    }


class TestConcatenatorRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "field.b",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other source_fields",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "even_another_field"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other output_field",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "wrong_target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other separator",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": ".",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause overwrite_target is true",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": ".",
                        "overwrite_target": True,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of delete_source_fields is true",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": ".",
                        "overwrite_target": False,
                        "delete_source_fields": True,
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule_1 = ConcatenatorRule._create_from_dict(specific_rule_definition)
        rule_2 = ConcatenatorRule._create_from_dict(other_rule_definition)
        assert (rule_1 == rule_2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                None,
                "correct rule definition",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": "False",
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "'overwrite_target' must be <class 'bool'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": "False",
                    },
                },
                TypeError,
                "'delete_source_fields' must be <class 'bool'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": "i should be a list",
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "'source_fields' must be <class 'list'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", 5, "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "'source_fields' must be <class 'str'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                ValueError,
                "Length of 'source_fields' must be => 2: 1",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": 5,
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "'target_field' must be <class 'str'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": 5,
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "'separator' must be <class 'str'>",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                        "some": "unknown_field",
                    },
                },
                TypeError,
                "got an unexpected keyword argument 'some'",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                TypeError,
                "missing 1 required keyword-only argument: 'separator'",
            ),
            (
                {
                    "filter": "field.a",
                    "concatenator": ["Not a dict configuration ..."],
                },
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, raised, message):
        if raised:
            with pytest.raises(raised, match=message):
                _ = ConcatenatorRule._create_from_dict(rule_definition)
        else:
            extractor_rule = ConcatenatorRule._create_from_dict(rule_definition)
            assert isinstance(extractor_rule, ConcatenatorRule)

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = ConcatenatorRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)
