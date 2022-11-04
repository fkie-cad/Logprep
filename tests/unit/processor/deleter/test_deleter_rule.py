# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from typing import Hashable
from unittest import mock
import pytest

from logprep.processor.deleter.rule import DeleterRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "test",
        "delete": True,
        "description": "my reference rule",
    }


class TestDeleterRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {"filter": "test", "delete": True, "description": "my reference rule"},
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {"filter": "other_filter", "delete": True, "description": "my reference rule"},
                False,
            ),
            (
                "Should be not equal cause of other delete bool",
                {"filter": "test", "delete": False, "description": "my reference rule"},
                False,
            ),
            (
                "Should be not equal cause other filter and other delete bool",
                {"filter": "other_filter", "delete": False, "description": "my reference rule"},
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = DeleterRule._create_from_dict(
            specific_rule_definition,
        )

        print(other_rule_definition)
        rule2 = DeleterRule._create_from_dict(
            other_rule_definition,
        )

        assert (rule1 == rule2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {"filter": "test", "delete": True, "description": "my reference rule"},
                None,
                "valid rule",
            ),
            (
                {"filter": "test", "delete": "yes", "description": "my reference rule"},
                TypeError,
                "'delete' must be <class 'bool'>",
            ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, raised, message):
        with mock.patch("os.path.isfile", return_value=True):
            if raised:
                with pytest.raises(raised, match=message):
                    _ = DeleterRule._create_from_dict(rule_definition)
            else:
                with mock.patch("builtins.open", mock.mock_open(read_data="")):
                    dropper_rule = DeleterRule._create_from_dict(rule_definition)
                    assert isinstance(dropper_rule, DeleterRule)

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = DeleterRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": "field.a",
            "delete": True,
            "description": "",
        }
        with pytest.deprecated_call() as warnings:
            DeleterRule._create_from_dict(rule_dict)
            assert len(warnings.list) == 1
            matches = [warning.message.args[0] for warning in warnings.list]
            assert "delete is deprecated. Use deleter.delete instead" in matches[0]
