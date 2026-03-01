# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-locals

import math
import re
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.calculator.fourFn import BNF
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.calculator.test_calculator import (
    failure_test_cases as non_ng_failure_testcases,
)
from tests.unit.processor.calculator.test_calculator import (
    test_cases as non_ng_testcases,
)

test_cases = deepcopy(non_ng_testcases)
failure_test_cases = deepcopy(non_ng_failure_testcases)


class TestCalculator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
        assert event.data == expected, testcase

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
            ("from_hex(4B)", 75),
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
        bnf = BNF()
        _ = bnf.parseString(expression, parseAll=True)  # pylint: disable=E1123,E1121
        result = bnf.evaluate_stack()
        assert result == expected
