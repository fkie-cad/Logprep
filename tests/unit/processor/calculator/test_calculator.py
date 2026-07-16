# pylint: disable=missing-docstring
# pylint: disable=too-many-positional-arguments
import math
import re

import pytest
from pyparsing import ParseException

from logprep.processor.calculator.fourFn import BNF
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is greater than (>)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not greater than (>)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>=2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is greater equal (>=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2>=3",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not greater equal (>=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is less than (<)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not less than (<)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1<=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is less equal (<=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2<=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not less equal (<=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1==1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is equal (==)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1==2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not equal (==)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1!=2",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare is unequal (!=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1!=1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": False},
        id="compare is not unequal (!=)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1 + 2 < 4",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare arithmetical less than (x+y < Z)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "2 ^ 3 > 4",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": True},
        id="compare expo greater than (x^y > Z)",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+1",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": 2},
        id="sums integers",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "1"},
        {"message": "This is a message", "field1": "1", "new_field": 2},
        id="sums integers from single field",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "1+${field1}+${field2}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "1.2", "field2": 4.5},
        {"message": "This is a message", "field1": "1.2", "field2": 4.5, "result": 6.7},
        id="sums floats from multiple fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2"},
        {"message": "This is a message", "field1": "3", "field2": 5, "field3": "2", "result": 13},
        id="multiplies before sum",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "${field1} + ${field2} * ${field3}",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": 8},
        id="do not raise if field value is 0",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "0", "field2": "4", "field3": 2},
        {"field1": "0", "field2": "4", "field3": 2, "result": False},
        id="logical evaluates fields to False",
    ),
    pytest.param(
        {
            "filter": "field2 AND field3",
            "calculator": {
                "calc": "all(${field1}, ${field2}, ${field3})",
                "target_field": "result",
            },
        },
        {"field1": "6", "field2": "4", "field3": 2},
        {"field1": "6", "field2": "4", "field3": 2, "result": True},
        id="logical evaluates fields",
    ),
    pytest.param(
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
        id="overwrites target",
    ),
    pytest.param(
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
        id="delete source fields",
    ),
    pytest.param(
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
        id="extend list",
    ),
    pytest.param(
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
        id="handles dotted fields",
    ),
    pytest.param(
        {
            "filter": "*",
            "calculator": {
                "calc": "${field\\\\1} + ${key.field\\\\2}"
                "+${key.sou\\\\rce.sou\\\\rce\\.\\\\field3}",
                "target_field": "wrapper.calc\\.res\\\\ult",
                "delete_source_fields": True,
            },
        },
        {"key": {"sou\\rce": {"sou\\rce.\\field3": 2}, "field\\2": 6}, "field\\1": 4},
        {"wrapper": {"calc.res\\ult": 12}},
        id="handles dotted fields & escaping in basic operands",
    ),
    pytest.param(
        {
            "filter": "*",
            "calculator": {
                "calc": "${spec.calc\\.op\\\\erator}(${spec.ca\\\\lc\\.value})",
                "target_field": "result",
                "delete_source_fields": True,
            },
        },
        {"spec": {"calc.op\\erator": "round", "ca\\lc.value": "PI"}},
        {"result": 3},
        id="handles dotted fields & escaping in operators",
    ),
    pytest.param(
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
        id="Time conversion ms -> ns",
    ),
    pytest.param(
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
        id="Ignore missing source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "ff"},
        {"message": "This is a message", "field1": "ff", "new_field": 255},
        id="convert hex to int",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "0xff"},
        {"message": "This is a message", "field1": "0xff", "new_field": 255},
        id="convert hex to int with prefix",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "from_hex(0x${field1})",
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "field1": "FF"},
        {"message": "This is a message", "field1": "FF", "new_field": 255},
        id="convert hex to int with prefix",
    ),
]


failure_test_cases = [
    pytest.param(
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
        id="Tags failure if parse is not possible",
    ),
    pytest.param(
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
        id="Tags failure if target_field exist",
    ),
    pytest.param(
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
        id="Tags failure if source_field missing",
    ),
    pytest.param(
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
        id="Tags failure if source_field is empty",
    ),
    pytest.param(
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
        id="Tags failure try to escape",
    ),
    pytest.param(
        {
            "filter": "field1",
            "calculator": {
                "calc": "round(${field1}",
                "target_field": "result",
            },
        },
        {"field1": 1337},
        {
            "field1": 1337,
            "tags": ["_calculator_failure"],
        },
        r"ProcessingWarning.*could not be parsed",
        id="Tags failure incorrect syntax",
    ),
    pytest.param(
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
        id="division by zero",
    ),
    pytest.param(
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
        },  # "STREAM ioctl timeout" for MacOS/darwin
        r"ProcessingWarning.*(Timer expired|ioctl timeout)",
        id="raises timout",
    ),
]


class TestCalculator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)

        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
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

    @pytest.mark.parametrize(
        "expression",
        [
            "1 < 2 < 3",
            "1 < 2 == 2",
        ],
    )
    def test_fourfn_rejects_chained_comparisons(self, expression):
        bnf = BNF()

        with pytest.raises(ParseException):
            bnf.parseString(expression, parseAll=True)  # pylint: disable=E1123,E1121

    @pytest.mark.parametrize(
        "expression",
        [
            "(1 < 2) + 1",
            "1 + (1 < 2)",
            "-(1 < 2)",
            "(1 < 2) == (2 < 3)",
            "all(1, 1) * 2",
        ],
    )
    def test_fourfn_rejects_boolean_operands(self, expression):
        bnf = BNF()
        bnf.parseString(expression, parseAll=True)  # pylint: disable=E1123,E1121

        with pytest.raises(
            Exception,
            match="boolean values cannot be used as operands",
        ):
            bnf.evaluate_stack()

    def test_fourfn_builds_expected_postfix_stack(self):
        """
        Ensure that expressions are converted into the expected execution order.

        The test protects the existing postfix stack structure so that future parser
        changes do not alter the evaluation order unintentionally. Intentional changes
        to the order must also update this test.
        """
        bnf = BNF()
        expression = "round((PI + 2) * 3 ^ 2 ^ 2 / 4 - -5, 2) >= multiply(2, 3) + E"

        bnf.parseString(expression, parseAll=True)  # pylint: disable=E1123,E1121

        assert bnf.exprStack == [
            "PI",
            "2",
            "+",
            "3",
            "2",
            "2",
            "^",
            "^",
            "*",
            "4",
            "/",
            "5",
            "unary -",
            "-",
            "2",
            ("round", 2),
            "2",
            "3",
            ("multiply", 2),
            "E",
            "+",
            ">=",
        ]

    @pytest.mark.parametrize(
        "failing_expression",
        [
            pytest.param("1 +", id="parse error"),
            pytest.param("1 / 0", id="evaluation error"),
        ],
    )
    def test_calculator_clears_expression_stack_after_failure(
        self,
        failing_expression,
    ):
        rule = {
            "filter": "field1",
            "calculator": {
                "calc": "${field1}",
                "target_field": "result",
            },
        }
        self._load_rule(rule)

        bnf = self.object.bnf
        failing_event = {"field1": failing_expression}

        result = self.object.process(failing_event)

        assert len(result.warnings) == 1
        assert self.object.bnf is bnf
        assert bnf.exprStack == []

        valid_event = {"field1": "2 + 3"}

        result = self.object.process(valid_event)

        assert result.warnings == []
        assert valid_event == {
            "field1": "2 + 3",
            "result": 5,
        }
        assert self.object.bnf is bnf
        assert bnf.exprStack == []
