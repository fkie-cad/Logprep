# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable
from unittest import mock
import pytest

from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.dropper.rule import (
    DropperRule,
    InvalidDropperDefinition,
)


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "test",
        "drop": ["field1", "field2"],
        "description": "my reference rule",
    }


class TestDropperRule:
    def test_rule_has_fields_to_drop(self, specific_rule_definition):
        rule = DropperRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["drop"],
        )
        fields_to_drop = rule.fields_to_drop
        assert isinstance(fields_to_drop, list)
        assert "field1" in fields_to_drop

    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {"filter": "test", "drop": ["field1", "field2"]},
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {"filter": "other_filter", "drop": ["field1", "field2"]},
                False,
            ),
            (
                "Should be not equal cause of one drop element is missing",
                {"filter": "test", "drop": ["field1"]},
                False,
            ),
            (
                "Should be not equal cause other drop fields",
                {"filter": "test", "drop": ["field1", "field3"]},
                False,
            ),
            (
                "Should be equal cause drop_full is the same (enabled by default)",
                {"filter": "test", "drop": ["field1", "field2"], "drop_full": True},
                True,
            ),
            (
                "Should be not equal cause drop_full is different (enabled by default)",
                {"filter": "test", "drop": ["field1", "field2"], "drop_full": False},
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = DropperRule._create_from_dict(
            specific_rule_definition,
        )

        print(other_rule_definition)
        rule2 = DropperRule._create_from_dict(
            other_rule_definition,
        )

        assert (rule1 == rule2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {"filter": "test", "drop": ["field1", "field2"]},
                None,
                "drop field with list exists",
            ),
            (
                {"filter": "test"},
                InvalidRuleDefinitionError,
                r"Keys \['filter'\] must be \['filter', 'drop'\]",
            ),
            (
                {"filter": "test", "drop": "field1, field2"},
                InvalidDropperDefinition,
                "is not a list",
            ),
            (
                {"filter": "test", "drop": {"field1": "field2"}},
                InvalidDropperDefinition,
                "is not a list",
            ),
            (
                {"filter": "test", "drop": ["field1", "field2"], "drop_full": True},
                None,
                "drop field with list exists and drop_full is bool",
            ),
            (
                {"filter": "test", "drop": ["field1", "field2"], "drop_full": "True"},
                InvalidDropperDefinition,
                'drop_full value "True" is not a bool!',
            ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, raised, message):
        with mock.patch("os.path.isfile", return_value=True):
            if raised:
                with pytest.raises(raised, match=message):
                    _ = DropperRule._create_from_dict(rule_definition)
            else:
                with mock.patch("builtins.open", mock.mock_open(read_data="")):
                    dropper_rule = DropperRule._create_from_dict(rule_definition)
                    assert isinstance(dropper_rule, DropperRule)

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = DropperRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)
