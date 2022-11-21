# pylint: disable=missing-docstring
import math
import pytest
from logprep.processor.calculator.fourFn import BNF, evaluate_stack, exprStack
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = [  # testcase, rule, event, expected
    (
        "sums integers",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": 2},
    ),
    (
        "sums integers from single field",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "1"},
        {"message": "This is a message", "field1": "1", "new_field": 2},
    ),
    (
        "sums floats from multiple fields",
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}+${field2}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "1.2", "field2": 4.5},
        {"message": "This is a message", "field1": "1.2", "field2": 4.5, "result": 6.7},
    ),
    (
        "multiplies before sum",
        {
            "filter": "message",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2"},
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2", "result": 13},
    ),
]


class TestCalculator(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "calculator",
        "specific_rules": ["tests/testdata/unit/calculator/specific_rules"],
        "generic_rules": ["tests/testdata/unit/calculator/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("9", 9),
            ("-9", -9),
            ("--9", 9),
            ("-E", -math.e),
            ("9 + 3 + 6", 9 + 3 + 6),
            ("9 + 3 / 11", 9 + 3.0 / 11),
            ("(9 + 3)", (9 + 3)),
            ("(9+3) / 11", (9 + 3.0) / 11),
            ("9 - 12 - 6", 9 - 12 - 6),
            ("9 - (12 - 6)", 9 - (12 - 6)),
            ("2*3.14159", 2 * 3.14159),
            ("3.1415926535*3.1415926535 / 10", 3.1415926535 * 3.1415926535 / 10),
            ("PI * PI / 10", math.pi * math.pi / 10),
            ("PI*PI/10", math.pi * math.pi / 10),
            ("PI^2", math.pi**2),
            ("round(PI^2)", round(math.pi**2)),
            ("6.02E23 * 8.048", 6.02e23 * 8.048),
            ("e / 3", math.e / 3),
            ("sin(PI/2)", math.sin(math.pi / 2)),
            ("10+sin(PI/4)^2", 10 + math.sin(math.pi / 4) ** 2),
            ("trunc(E)", int(math.e)),
            ("trunc(-E)", int(-math.e)),
            ("round(E)", round(math.e)),
            ("round(-E)", round(-math.e)),
            ("E^PI", math.e**math.pi),
            ("exp(0)", 1),
            ("exp(1)", math.e),
            ("2^3^2", 2**3**2),
            ("(2^3)^2", (2**3) ** 2),
            ("2^3+2", 2**3 + 2),
            ("2^3+5", 2**3 + 5),
            ("2^9", 2**9),
            ("sgn(-2)", -1),
            ("sgn(0)", 0),
            ("sgn(0.1)", 1),
            ("round(E, 3)", round(math.e, 3)),
            ("round(PI^2, 3)", round(math.pi**2, 3)),
            ("sgn(cos(PI/4))", 1),
            ("sgn(cos(PI/2))", 0),
            ("sgn(cos(PI*3/4))", -1),
            ("+(sgn(cos(PI/4)))", 1),
            ("-(sgn(cos(PI/4)))", -1),
            ("hypot(3, 4)", 5),
            ("multiply(3, 7)", 21),
            ("all(1,1,1)", True),
            ("all(1,1,1,1,1,0)", False),
        ],
    )
    def test_fourfn(self, expression, expected):
        _ = BNF().parseString(expression, parseAll=True)
        result = evaluate_stack(exprStack[:])
        assert result == expected
