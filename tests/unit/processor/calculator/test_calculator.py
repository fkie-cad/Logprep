# pylint: disable=missing-docstring
import math
import re

import pytest

from logprep.processor.calculator.fourFn import BNF
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
    (
        "do not raise if field value is 0",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": 8},
    ),
    (
        "logical evaluates fields to False",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": False},
    ),
    (
        "logical evaluates fields",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"field1": "6", "field2": "4", "field3": 2, "result": True},
    ),
    (
        "overwrites target",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "field1",
                "overwrite_target": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"field1": 12, "field2": "4", "field3": 2},
    ),
    (
        "delete source fields",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"result": 12},
    ),
    (
        "extend list",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} +${field3}",
                "target_field": "target",
                "merge_with_target": True,
            },
        },
        {"field1": "6", "field2": "4", "field3": 2, "target": [1, 5, 3]},
        {"field1": "6", "field2": "4", "field3": 2, "target": [1, 5, 3, 12]},
    ),
    (
        "handles dotted fields",
        {
            "filter": "*",
            "calculator": {
                "calc": "${key.field1} + ${key.source.field2} +${key.source.source.field3}",
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"key": {"source": {"source": {"field3": 2}, "field2": 6}, "field1": 4}},
        {"result": 12},
    ),
    (
        "Time conversion ms -> ns",
        {
            "filter": "duration",
            "calculator": {
                "calc": "${duration} * 10e5",
                "target_field": "duration",
                "overwrite_target": True,
            },
        },
        {"duration": "0.01"},
        {"duration": 10000.0},
    ),
    (
        "Ignore missing source fields",
        {
            "filter": "duration",
            "calculator": {
                "calc": "${missing_field} * 10e5",
                "target_field": "duration",
                "ignore_missing_fields": True,
            },
        },
        {"duration": "0.01"},
        {"duration": "0.01"},
    ),
    (
        "convert hex to int",
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "ff"},
        {"message": "This is a message", "field1": "ff", "new_field": 255},
    ),
    (
        "convert hex to int with prefix",
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "0xff"},
        {"message": "This is a message", "field1": "0xff", "new_field": 255},
    ),
    (
        "convert hex to int with prefix",
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "FF"},
        {"message": "This is a message", "field1": "FF", "new_field": 255},
    ),
]


failure_test_cases = [  # testcase, rule, event, expected, error_message
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "not parsable", "field2": "4", "field3": 2},
        {
            "field1": "not parsable",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*expression 'not parsable \+ 4 \* 2' could not be parsed",
    ),
    (
        "Tags failure if target_field exist",
        {
            "filter": "field1 AND field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "5", "field2": "4", "field3": 2, "result": "exists"},
        {
            "field1": "5",
            "field2": "4",
            "field3": 2,
            "result": "exists",
            "tags": ["_calculator_failure"],
        },
        "FieldExistsWarning.*one or more subfields existed and could not be extended: result",
    ),
    (
        "Tags failure if source_field missing",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field2": "4", "field3": 2},
        {
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_missing_field_warning"],
        },
        r"ProcessingWarning.*missing source_fields: \['field1']",
    ),
    (
        "Tags failure if source_field is empty",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "", "field2": "4", "field3": 2},
        {
            "field1": "",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*no value for fields: \['field1'\]",
    ),
    (
        "Tags failure try to escape",
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "\"; print('escaped');\"", "field2": "4", "field3": 2},
        {
            "field1": "\"; print('escaped');\"",
            "field2": "4",
            "field3": 2,
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*could not be parsed",
    ),
    (
        "division by zero",
        {
            "filter": "message",
            "calculator": {
                "calc": "3/0",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "1.2", "field2": 4.5},
        {
            "message": "This is a message",
            "field1": "1.2",
            "field2": 4.5,
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*'3/0' => '3/0' results in division by zero",
    ),
    (
        "raises timout",
        {
            "filter": "message",
            "calculator": {
                "calc": " 9^9^9",
                "target_field": "result",
            },
        },
        {"message": "This is a message"},
        {
            "message": "This is a message",
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*Timer expired",
    ),
]


class TestCalculator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        self._load_rule(rule)

        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
        assert event == expected, testcase

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
