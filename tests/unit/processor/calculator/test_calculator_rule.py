# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.calculator.rule import CalculatorRule


class TestCalculatorRule:
    def test_returns_rule(self):
        rule_dict = {
            "filter": "field1 AND field2",
            "calculator": {"calc": "${field1} + ${field2}", "target_field": "field3"},
        }
        rule = CalculatorRule._create_from_dict(rule_dict)
        assert rule

    def test_fills_source_fields(self):
        rule_dict = {
            "filter": "field1 AND field2",
            "calculator": {"calc": "${field1} + ${field2}", "target_field": "field3"},
        }
        rule = CalculatorRule._create_from_dict(rule_dict)
        assert rule.source_fields == ["field1", "field2"]

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "calculator": {"calc": "", "target_field": "new_field"},
                },
                ValueError,
                "Length of 'calc' must be >= 3: 0",
            ),
            (
                {
                    "filter": "message",
                    "calculator": {"calc": "1 + 1", "target_field": "new_field"},
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                CalculatorRule._create_from_dict(rule)
        else:
            rule_instance = CalculatorRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("calculator").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)
