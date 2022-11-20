from logprep.processor.calculator.rule import CalculatorRule


class TestCalculatorRule:
    def test_returns_rule(self):
        rule_dict = {
            "filter": "field1 AND field2",
            "calculator": {"calc": "%{field1} + %{field2}", "target_field": "field3"},
        }
        rule = CalculatorRule._create_from_dict(rule_dict)
        assert rule
