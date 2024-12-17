# pylint: disable=missing-docstring
# pylint: disable=protected-access
from typing import Hashable
from unittest import mock
import pytest

from logprep.processor.deleter.rule import DeleterRule


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "test",
        "deleter": {"delete": True},
        "description": "my reference rule",
    }


class TestDeleterRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {"filter": "test", "deleter": {"delete": True}, "description": "my reference rule"},
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "deleter": {"delete": True},
                    "description": "my reference rule",
                },
                False,
            ),
            (
                "Should be not equal cause of other delete bool",
                {
                    "filter": "test",
                    "deleter": {"delete": False},
                    "description": "my reference rule",
                },
                False,
            ),
            (
                "Should be not equal cause other filter and other delete bool",
                {
                    "filter": "other_filter",
                    "deleter": {"delete": False},
                    "description": "my reference rule",
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = DeleterRule._create_from_dict(
            rule_definition,
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
                {"filter": "test", "deleter": {"delete": True}, "description": "my reference rule"},
                None,
                "valid rule",
            ),
            (
                {
                    "filter": "test",
                    "deleter": {"delete": "yes"},
                    "description": "my reference rule",
                },
                TypeError,
                "'delete' must be <class 'bool'>",
            ),
            (
                {"filter": "test", "deleter": {"delete": True}, "description": "my reference rule"},
                None,
                None,
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
                    deleter_rule = DeleterRule._create_from_dict(rule_definition)
                    assert isinstance(deleter_rule, DeleterRule)

    def test_rule_is_hashable(self, rule_definition):
        rule = DeleterRule._create_from_dict(rule_definition)
        assert isinstance(rule, Hashable)
