# pylint: disable=missing-docstring
# pylint: disable=too-many-positional-arguments
import math

import pytest

from logprep.processor.calculator.fourFn import (
    DivisionByZeroError,
    InvalidSyntaxError,
    ParsingError,
    ValueType,
    compile_expression,
    parse_value,
)
from tests.unit.processor.base import BaseProcessorTestCase

static_expression_test_cases = [
    ("9", 9),
    ("-9", -9),
    ("--9", 9),
    ("-E", -math.e),
    ("9 + 3 + 6", 9 + 3 + 6),
    ("9 + 3 / 11", 9 + 3.0 / 11),
    ("15 + 10 % 3", 15 + 10 % 3),
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
    ("2^3^4", 2**3**4),
    ("(2^3)^4", (2**3) ** 4),
    ("2^3+2", 2**3 + 2),
    ("2^3+5", 2**3 + 5),
    ("2^9", 2**9),
    ("2 > 1", True),
    ("1 > 1", False),
    ("1 > 2", False),
    ("1 >= 1", True),
    ("1 >= 2", False),
    ("5 < 6", True),
    ("5 < 5", False),
    ("5 <= 5", True),
    ("1 < 2 < 3", True),
    ("1 < 1 < 3", False),
    ("1 < 3 < 3", False),
    ("1 <= 2 <= 3", True),
    ("1 <= 1 < 3", True),
    ("1 < 3 <= 3", True),
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
    ("all(3>2,2>1)", True),
    ("all(3>2,1>1)", False),
    ("all(1,1,1)", True),
    ("all(1,1,1,1,1,0)", False),
    ("any(3>2,2>1)", True),
    ("any(0,0,0,0)", False),
    ("any(0,0,0,1)", True),
    ("any(3>3,2>1)", True),
    ("any(3>3,2>2)", False),
]

dynamic_expression_testcases = [
    pytest.param(
        "${a}",
        {"a": 1337},
        1337,
        id="simple variable test (int)",
    ),
    pytest.param(
        "${a}",
        {"a": 1337.0},
        1337.0,
        id="simple variable test (float)",
    ),
    pytest.param(
        "${a}",
        {"a": "1337"},
        1337,
        id="simple variable test (str)",
    ),
    pytest.param(
        "${a.b.c}",
        {"a": {"b": {"c": 42}}},
        42,
        id="nested variable test",
    ),
    pytest.param(
        "${a} + ${b} * ${c}",
        {"a": 1, "b": 2.0, "c": "3"},
        7.0,
        id="arithmetic with variables (mixed types) test",
    ),
]

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

setup_failure_test_cases = [
    pytest.param(
        {
            "filter": "field1",
            "calculator": {
                "calc": "round(${field1}",
                "target_field": "result",
            },
        },
        InvalidSyntaxError,
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
        DivisionByZeroError,
        id="division by zero in expression",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": "3/(1-1)",
                "target_field": "result",
            },
        },
        DivisionByZeroError,
        id="division by zero on optimization",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": " 9^9^9",
                "target_field": "result",
            },
        },
        TimeoutError,
        id="constant raises timeout on setup",
    ),
]

runtime_failure_test_cases = [
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
        id="Tags failure try to escape",
    ),
    pytest.param(
        {
            "filter": "message",
            "calculator": {
                "calc": " ${a}^${a}^${a}",
                "target_field": "result",
            },
        },
        {"message": "This is a message", "a": 9},
        {
            "message": "This is a message",
            "a": 9,
            "tags": ["_calculator_failure"],
        },  # "STREAM ioctl timeout" for MacOS/darwin
        id="raises timeout on runtime",
    ),
]


class TestCalculator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize(
        "from_type, to_type, can_cast",
        [
            (ValueType.NUMBER, ValueType.NUMBER, True),
            (ValueType.BOOLEAN, ValueType.BOOLEAN, True),
            (ValueType.NUMBER, ValueType.BOOLEAN, True),
            (ValueType.BOOLEAN, ValueType.NUMBER, False),
        ],
    )
    def test_casting_rules_for_value_type(self, from_type, to_type, can_cast):
        assert from_type.can_be_cast_to(to_type) == can_cast

    @pytest.mark.parametrize(
        "input, to_type, result",
        [
            (1337, ValueType.NUMBER, 1337),
            (42.0, ValueType.NUMBER, 42.0),
            ("1337", ValueType.NUMBER, 1337),
            ("2e-3", ValueType.NUMBER, 0.002),
            ("pi", ValueType.NUMBER, math.pi),
            ("PI", ValueType.NUMBER, math.pi),
            ("E", ValueType.NUMBER, math.e),
            ("e", ValueType.NUMBER, math.e),
            (0, ValueType.BOOLEAN, False),
            (0.1, ValueType.BOOLEAN, True),
            (1, ValueType.BOOLEAN, True),
            (-1, ValueType.BOOLEAN, True),
        ],
    )
    def test_parse_value(self, input, to_type, result):
        assert parse_value(input, to_type) == result

    @pytest.mark.parametrize(
        "value, to_type",
        [
            ("", ValueType.NUMBER),
            (None, ValueType.NUMBER),
            ("", ValueType.BOOLEAN),
            (None, ValueType.BOOLEAN),
        ],
    )
    def test_parse_values_fails(self, value, to_type):
        with pytest.raises(ParsingError):
            parse_value(value, to_type)

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected", runtime_failure_test_cases)
    def test_testcases_failure_handling_at_runtime(self, rule, event, expected):
        self._load_rule(rule)
        self.object.setup()
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert event == expected

    @pytest.mark.parametrize("rule, error_type", setup_failure_test_cases)
    def test_testcases_failure_handling_at_setup(self, rule, error_type):
        self._load_rule(rule)
        with pytest.raises(error_type):
            self.object.setup()

    @pytest.mark.parametrize(
        "expression, expected",
        static_expression_test_cases,
    )
    def test_static_expression(self, expression, expected):
        program = compile_expression(expression)
        print(program.get_diagram())
        result = program.evaluate({})
        assert result == expected

    @pytest.mark.parametrize(
        "expression, expected",
        static_expression_test_cases,
    )
    def test_static_expression_optimized(self, expression, expected):
        program = compile_expression(expression)
        program_optimized = program.optimize()
        result = program_optimized.evaluate({})
        assert result == expected

    @pytest.mark.parametrize(
        "expression,context,expected",
        dynamic_expression_testcases,
    )
    def test_dynamic_expressions(self, expression, context, expected):
        program = compile_expression(expression)
        result = program.evaluate(context)
        assert result == expected

    @pytest.mark.parametrize(
        "expression,context,expected",
        dynamic_expression_testcases,
    )
    def test_dynamic_expressions_optimized(self, expression, context, expected):
        program = compile_expression(expression)
        program_optimized = program.optimize()
        result = program_optimized.evaluate(context)
        assert result == expected

    @pytest.mark.parametrize(
        "expression",
        [
            "1 < 2 == 2",
        ],
    )
    def test_fourfn_rejects_chained_comparisons(self, expression):

        with pytest.raises(InvalidSyntaxError):
            prog = compile_expression(expression)
            print(prog.get_diagram())

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
        with pytest.raises(InvalidSyntaxError):
            compile_expression(expression)

    def test_builds_expected_ast(self):
        program = compile_expression("10 * cos( ${t} * pi + ${phase}) > 1 + 2 * (3 + 4)")
        diagram = program.get_diagram()
        with open("tests/testdata/unit/calculator/ast/diagram.gv", "r", encoding="utf-8") as fp:
            expected = fp.read()
        assert diagram == expected
