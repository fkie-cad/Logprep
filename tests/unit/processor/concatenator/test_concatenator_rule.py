# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable

import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.concatenator.rule import ConcatenatorRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "field.a",
        "concatenator": {
            "source_fields": ["field.a", "field.b", "other_field.c"],
            "target_field": "target_field",
            "seperator": "-",
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
                        "seperator": "-",
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
                        "seperator": "-",
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
                        "seperator": "-",
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
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other seperator",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "seperator": ".",
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
                        "seperator": ".",
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
                        "seperator": ".",
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
        rule1_config = ConcatenatorRule.Config(specific_rule_definition["concatenator"])
        rule1 = ConcatenatorRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            rule1_config,
        )
        rule2_config = ConcatenatorRule.Config(other_rule_definition["concatenator"])
        rule2 = ConcatenatorRule(
            LuceneFilter.create(other_rule_definition["filter"]),
            rule2_config,
        )
        assert (rule1 == rule2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "seperator": "-",
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
                        "seperator": "-",
                        "overwrite_target": "False",
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "The field 'overwrite_target' should be of type 'bool', but is '<class 'str'>'",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": "False",
                    },
                },
                    ValueError,
                "The field '.*' should be of type 'bool', but is '<class 'str'>'",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": "i should be a list",
                        "target_field": "target_field",
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "The field 'source_fields' should be of type 'list', but is '<class 'str'>'",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", 5, "other_field.c"],
                        "target_field": "target_field",
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "the list also contains non 'str' values",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a"],
                        "target_field": "target_field",
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "At least two source fields should be given for the concatenation.",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": 5,
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "The field 'target_field' should be of type 'str', but is '<class 'int'>'",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "seperator": 5,
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                    ValueError,
                "The field 'seperator' should be of type 'str', but is '<class 'int'>'",
            ),
            (
                    {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "seperator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                        "some": "unknown_field",
                    },
                },
                    ValueError,
                "Unknown fields were given: 'some'",
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
                    ValueError,
                "Following fields were missing: 'seperator'",
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
