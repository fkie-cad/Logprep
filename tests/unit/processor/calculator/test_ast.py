# pylint: disable=missing-docstring
# pylint: disable=too-many-positional-arguments
import math
import re

import pytest

from logprep.processor.calculator.ast.exceptions import (
    DivisionByZeroError,
    InvalidSyntaxError,
    ParsingError,
    UnknownFunctionError,
)
from logprep.processor.calculator.ast.node import get_ast_diagram
from logprep.processor.calculator.ast.parse import parse_expression
from logprep.processor.calculator.ast.util import (
    ValueType,
    parse_value,
    read_hex_number,
)

static_expression_example_test_cases = [
    ("123", 123),
    ("-E", -math.e),
    ("pi * 1e9", math.pi * 1e9),
    ("1 + 2 * 3", 7),
    ("(1 + 2) * 3", 9),
    ("3 / 2", 1.5),
    ("3 % 2", 1),
    ("0x2a", 42),
    ("from_hex(2A)", 42),
    ("1 == 1", True),
    ("1 == 1.0000001", False),
    ("1 != 1.0000001", True),
    ("1 > 2", False),
    ("1 < 2", True),
    ("2 >= 2", True),
    ("2 <= 2", True),
    ("1 < 2 < 3", True),
    ("round(pi, 3)", 3.142),
    ("hypot(3, 4)", 5),
    ("-(SIGN(COS(PI/4)))", -1),
    ("all(1,1,1,0)", False),
    ("any(0,0,0,1)", True),
    ("not(1==1)", False),
    ("AND(1 < 2 < 3,NOT( 5 > 6))", True),
]

static_expression_test_cases = static_expression_example_test_cases + [
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
    ("0 - 5", -5),
    ("2*3.14159", 2 * 3.14159),
    ("3.1415926535*3.1415926535 / 10", 3.1415926535 * 3.1415926535 / 10),
    ("PI * PI / 10", math.pi * math.pi / 10),
    ("PI*PI/10", math.pi * math.pi / 10),
    ("PI^2", math.pi**2),
    ("round(PI^2)", round(math.pi**2)),
    ("6.02E23 * 8.048", 6.02e23 * 8.048),
    ("e / 3", math.e / 3),
    ("5 % 2", 5 % 2),
    ("sin(PI/2)", math.sin(math.pi / 2)),
    ("10+sin(PI/4)^2", 10 + math.sin(math.pi / 4) ** 2),
    ("trunc(E)", int(math.e)),
    ("trunc(-E)", int(-math.e)),
    ("from_hex(4B)", 75),
    ("round(E)", round(math.e)),
    ("Round(e)", round(math.e)),
    ("ROUND(e)", round(math.e)),
    ("round(-E)", round(-math.e)),
    ("E^PI", math.e**math.pi),
    ("exp(0)", 1),
    ("exp(1)", math.e),
    ("2^3^4", 2**3**4),
    ("(2^3)^4", (2**3) ** 4),
    ("2^3+2", 2**3 + 2),
    ("2^3+5", 2**3 + 5),
    ("2^9", 2**9),
    ("1 != 1", False),
    ("1 != 1.001", True),
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
    ("FROM_HEX(2a)", 42),
    ("From_Hex(2A)", 42),
    ("sgn(-2)", -1),
    ("sgn(0)", 0),
    ("sgn(0.1)", 1),
    ("round(E, 3)", round(math.e, 3)),
    ("round(PI^2, 3)", round(math.pi**2, 3)),
    ("sgn(cos(PI/4))", 1),
    ("sgn(cos(PI/2))", 0),
    ("sgn(cos(PI*3/4))", -1),
    ("+(sgn(cos(PI/4)))", 1),
    ("multiply(3, 7)", 21),
    ("all(3>2,2>1)", True),
    ("all(3>2,1>1)", False),
    ("all(1,1,1)", True),
    ("all(1,1,1,1,1,0)", False),
    ("any(3>2,2>1)", True),
    ("any(0,0,0,0)", False),
    ("any(3>3,2>1)", True),
    ("any(3>3,2>2)", False),
    ("all(1*2,2*1,2/1,1+0,0+1,1-0)", True),
    ("any(0*4,0/2,0%2)", False),
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
    pytest.param(
        "all(${a} + 0 == ${a}, 0 + ${a} == ${a})",
        {"a": 1},
        True,
        id="trigger addition optimizations",
    ),
    pytest.param(
        "all(0 - ${a} == - ${a}, ${a} - 0 == ${a}, ${a} - ${a} == 0)",
        {"a": 1},
        True,
        id="trigger subtraction optimizations",
    ),
    pytest.param(
        "all(${a} * 1, 1 * ${a}, ${a} / 1, ${a} % 2)",
        {"a": 5},
        True,
        id="trigger multiplication optimizations",
    ),
    pytest.param(
        "any(0 * 0, 0 * ${a}, ${a} * 0)",
        {"a": 1},
        False,
        id="trigger multiplication optimizations 2",
    ),
    pytest.param(
        "all(${a}^0==1, 1^${a} == 1, ${a}^1 == ${a})",
        {"a": 5},
        True,
        id="trigger power optimizations",
    ),
    pytest.param(
        "(1 + 1) / ${b}",
        {"b": 4},
        0.5,
        id="trigger partial operand optimization",
    ),
    pytest.param(
        "(1 -1 ) - (${a} - 0)",
        {"a": 123},
        -123,
        id="trigger subtraction optimization",
    ),
    pytest.param(
        "-(1 + ${b}) < ${b}",
        {"b": 4},
        True,
        id="trigger partial operand optimization",
    ),
    pytest.param(
        "round(${a} * pi, 2)",
        {"a": 2},
        6.28,
        id="trigger function parameter optimization",
    ),
    pytest.param(
        "all(${a}, 1 < 0)",
        {"a": 123},
        False,
        id="trigger all optimization",
    ),
    pytest.param(
        "any(${a}, 1 == 1)",
        {"a": 0},
        True,
        id="trigger any optimization",
    ),
    pytest.param(
        "NOT(OR(${a}, 1 != 1))",
        {"a": 1},
        False,
        id="trigger not optimization",
    ),
    pytest.param(
        "1 < ${b} < (1 + 2)",
        {"b": 2},
        True,
        id="trigger partial range optimization",
    ),
]


class TestAST:
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
            ("nope", ValueType.NUMBER),
            (True, ValueType.NUMBER),
            (False, ValueType.NUMBER),
            ([], ValueType.NUMBER),
            (["123"], ValueType.NUMBER),
            ({}, ValueType.NUMBER),
            ({"123": 123}, ValueType.NUMBER),
            ("", ValueType.BOOLEAN),
            (None, ValueType.BOOLEAN),
            ("True", ValueType.BOOLEAN),
            ("true", ValueType.BOOLEAN),
            ("TRUE", ValueType.BOOLEAN),
            ([], ValueType.BOOLEAN),
            ([True], ValueType.BOOLEAN),
            ({}, ValueType.BOOLEAN),
            ({"True": True}, ValueType.BOOLEAN),
            (123, None),
        ],
    )
    def test_parse_values_fails(self, value, to_type):
        with pytest.raises(ParsingError):
            parse_value(value, to_type)

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "nope",
            True,
            False,
            123,
            12.3,
            [],
            ["FF"],
            {},
            {"ff": "ff"},
        ],
    )
    def test_read_hex_number_raises(self, value):
        with pytest.raises(ParsingError):
            read_hex_number(value)

    @pytest.mark.parametrize(
        "expression, expected",
        static_expression_test_cases,
    )
    def test_static_expression(self, expression, expected):
        parsed = parse_expression(expression)
        result = parsed.evaluate({})
        assert result == expected

    @pytest.mark.parametrize(
        "expression, expected",
        static_expression_test_cases,
    )
    def test_static_expression_optimized(self, expression, expected):
        parsed = parse_expression(expression)
        parsed_optimized = parsed.optimize()
        result = parsed_optimized.evaluate({})
        assert result == expected

    @pytest.mark.parametrize(
        "expression,context,expected",
        dynamic_expression_testcases,
    )
    def test_dynamic_expressions(self, expression, context, expected):
        parsed = parse_expression(expression)
        result = parsed.evaluate(context)
        assert result == expected

    @pytest.mark.parametrize(
        "expression,context,expected",
        dynamic_expression_testcases,
    )
    def test_dynamic_expressions_optimized(self, expression, context, expected):
        parsed = parse_expression(expression)
        parsed_optimized = parsed.optimize()
        result = parsed_optimized.evaluate(context)
        assert result == expected

    @pytest.mark.parametrize(
        "expression,error_type",
        [
            ("(1 < 2) + 1", InvalidSyntaxError),
            ("1 + (1 < 2)", InvalidSyntaxError),
            ("-(1 < 2)", InvalidSyntaxError),
            ("unknown()", UnknownFunctionError),
            ("unknown(1,2,3)", UnknownFunctionError),
            ("cos()", InvalidSyntaxError),
            ("cos(1, 2)", InvalidSyntaxError),
            ("(1 < 2) == (2 < 3)", InvalidSyntaxError),
            ("all(1, 1) * 2", InvalidSyntaxError),
            ("1 < 2 == 2", InvalidSyntaxError),
            ("1 < 2 < 3 < 4", InvalidSyntaxError),
        ],
    )
    def test_invalid_syntax_raises(self, expression, error_type):
        with pytest.raises(error_type):
            parse_expression(expression)

    @pytest.mark.parametrize(
        "expression",
        [
            "${a} / (1-1)",
            "${a} % (1-1)",
            "0^-1",
        ],
    )
    def test_division_by_zero_on_optimization_raises(self, expression):
        parsed = parse_expression(expression)
        with pytest.raises(DivisionByZeroError):
            parsed.optimize()

    @pytest.mark.parametrize(
        "expression",
        [
            "${a} / (1-1)",
            "${a} % (1-1)",
            "0 ^ -(${a})",
        ],
    )
    def test_division_by_zero_on_evaluate(self, expression):
        parsed = parse_expression(expression)
        with pytest.raises(DivisionByZeroError):
            parsed.evaluate({"a": 2})

    def test_get_ast_diagram(self):
        parsed = parse_expression("10 * cos( ${t} * pi + ${phase}) > 1 + 2 * (3 + 4)")
        diagram = get_ast_diagram(parsed)
        expected = """
            digraph {
                n0 [label = "<op '>'>";];
                n1 [label = "<op '*'>";];
                n2 [label = "<constant 10>";];
                n3 [label = "<func 'cos'>";];
                n4 [label = "<op '+'>";];
                n5 [label = "<op '*'>";];
                n6 [label = "<variable 't'>";];
                n7 [label = "<constant 3.141592653589793>";];
                n8 [label = "<variable 'phase'>";];
                n9 [label = "<op '+'>";];
                n10 [label = "<constant 1>";];
                n11 [label = "<op '*'>";];
                n12 [label = "<constant 2>";];
                n13 [label = "<op '+'>";];
                n14 [label = "<constant 3>";];
                n15 [label = "<constant 4>";];
                n0 -> n1;
                n0 -> n9;
                n1 -> n2;
                n1 -> n3;
                n3 -> n4;
                n4 -> n5;
                n4 -> n8;
                n5 -> n6;
                n5 -> n7;
                n9 -> n10;
                n9 -> n11;
                n11 -> n12;
                n11 -> n13;
                n13 -> n14;
                n13 -> n15;
            }
        """
        diagram, _ = re.subn(r"\s+", " ", diagram)
        expected, _ = re.subn(r"\s+", " ", expected)
        assert diagram.strip() == expected.strip()
