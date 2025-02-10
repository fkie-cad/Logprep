# pylint: disable=missing-docstring
from unittest import mock

import pytest

from logprep.processor.calculator.processor import Calculator
from logprep.processor.calculator.rule import CalculatorRule
from logprep.registry import Registry


class TestRegistry:

    def test_get_rule_class_returns_rule_class(self):
        expected_rule_class = CalculatorRule
        rule_definition = {"filter": "foo", "calculator": {}}
        assert Registry.get_rule_class_by_rule_definition(rule_definition) == expected_rule_class

    def test_get_rule_class_raises(self):
        with pytest.raises(ValueError, match="Unknown rule type"):
            Registry.get_rule_class_by_rule_definition({"filter": "foo", "i do not exist": {}})

    def test_get_rule_class_raises_on_wrong_type(self):
        with mock.patch.object(Registry, "mapping", {123: Calculator}):
            with pytest.raises(ValueError, match="Unknown rule type"):
                Registry.get_rule_class_by_rule_definition({"filter": "foo", 123: {}})

    def test_get_rule_class_raises_if_not_processor(self):
        with pytest.raises(ValueError, match="Unknown processor type"):
            Registry.get_rule_class_by_rule_definition({"filter": "foo", "console_output": {}})

    def test_get_rule_class_raises_if_no_rule_class(self):
        with mock.patch.object(Calculator, "rule_class", None):
            with pytest.raises(ValueError, match="Rule type not set in processor"):
                Registry.get_rule_class_by_rule_definition({"filter": "foo", "calculator": {}})

    def test_get_class(self):
        expected_class = Calculator
        assert Registry.get_class("calculator") == expected_class

    def test_get_class_raises(self):
        with pytest.raises(ValueError, match="Unknown processor type"):
            Registry.get_class("i do not exist")
