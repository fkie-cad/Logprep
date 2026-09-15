"""Functionality to parse expressions to an abstract syntax tree"""

from re import RegexFlag
from typing import Callable

from pyparsing import (
    CaselessKeyword,
    CaselessLiteral,
    DelimitedList,
    Forward,
    Group,
    Optional,
    ParseException,
    ParserElement,
    ParseResults,
    ParseSyntaxException,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    one_of,
)

from logprep.processor.calculator.ast.exceptions import (
    InvalidSyntaxError,
)
from logprep.processor.calculator.ast.function_registry import try_create_function_node
from logprep.processor.calculator.ast.node import (
    ARITHMETIC_OPERATORS,
    COMPARISON_OPERATORS,
    ASTNode,
    ConstantNumberASTNode,
    HexNumberVariableASTNode,
    NegateASTNode,
    RangeCheckASTNode,
    VariableASTNode,
)
from logprep.processor.calculator.ast.util import read_hex_number
from logprep.util.helper import VARIABLE_PATTERN

# All __build_* functions below serve as callbacks for the  pyparsing based
# syntax parser. They take a parsing result and convert it to an ASTNode.
# Pyparse will wrap those nodes in an PraseResults instance before further
# handling them.


def __build_constant(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1 and isinstance(parsed[0], str), parsed
    return ConstantNumberASTNode(parsed[0])


def __build_constant_from_hex(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1 and isinstance(parsed[0], str), parsed
    hex_number = read_hex_number(parsed[0])
    return ConstantNumberASTNode(hex_number)


def __build_variable(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1 and isinstance(parsed[0], str), parsed
    return VariableASTNode(parsed[0])


def __build_hex_variable(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1 and isinstance(parsed[0], str), parsed
    return HexNumberVariableASTNode(parsed[0])


def __build_atomic_expression(parsed: ParseResults) -> ASTNode:
    if len(parsed) == 1:
        if isinstance(parsed[0], ASTNode):
            return parsed[0]
        assert (
            isinstance(parsed[0], ParseResults)
            and len(parsed[0]) == 1
            and isinstance(parsed[0][0], ASTNode)
        ), parsed
        return parsed[0][0]

    assert len(parsed) >= 2, parsed
    *signs, node = parsed

    if isinstance(node, ParseResults):
        assert len(node) == 1, node
        node = node[0]
    assert isinstance(node, ASTNode), node

    assert all(sign in ("+", "-") for sign in signs), signs
    if len([s for s in signs if s == "-"]) % 2 == 1:
        return NegateASTNode(node)

    return node


def __build_function_call(parsed: ParseResults) -> ASTNode:
    assert len(parsed) >= 1

    function_name, *params = parsed
    assert isinstance(function_name, str), function_name
    assert all(isinstance(i, ParseResults) and len(i) == 1 for i in params) and all(
        isinstance(i[0], ASTNode) for i in params
    ), params
    return try_create_function_node(function_name, *(i[0] for i in params))


def __build_arithmetic_operation(parsed: ParseResults) -> ASTNode:
    assert len(parsed) > 0 and len(parsed) % 2 == 1

    lhs = parsed[0]
    assert isinstance(lhs, ASTNode), lhs

    for i in range(1, len(parsed), 2):
        operator_symbol, rhs = parsed[i], parsed[i + 1]
        assert isinstance(operator_symbol, str), operator_symbol
        assert isinstance(rhs, ASTNode), rhs
        assert operator_symbol in ARITHMETIC_OPERATORS
        operator_type = ARITHMETIC_OPERATORS[operator_symbol]
        lhs = operator_type(lhs, rhs)
    return lhs


def __build_comparison_operation(parsed: ParseResults) -> ASTNode:
    assert len(parsed) % 2 == 1 and all(
        isinstance(parsed[i], ASTNode) for i in range(0, len(parsed), 2)
    ), parsed
    if len(parsed) == 1:
        return parsed[0]

    if len(parsed) > 5:
        raise InvalidSyntaxError("Comparisons can not be chained.")

    if len(parsed) == 5:
        lower_bound, lower_op, value, upper_op, upper_bound = parsed

        assert isinstance(lower_bound, ASTNode), lower_bound
        assert isinstance(lower_op, str), lower_op
        assert isinstance(value, ASTNode), value
        assert isinstance(upper_op, str), upper_op
        assert isinstance(upper_bound, ASTNode), upper_bound
        if not all(op in ("<", "<=") for op in (lower_op, upper_op)):
            raise InvalidSyntaxError(
                "Range check required comparison to be '<' or '<='"
                f" got {lower_op !r} and {upper_op !r}."
            )
        return RangeCheckASTNode(
            lower_bound,
            value,
            upper_bound,
            lower_bound_is_inclusive=lower_op == "<=",
            upper_bound_is_inclusive=upper_op == "<=",
        )

    lhs = parsed[0]
    operator_symbol = parsed[1]
    rhs = parsed[2]
    assert isinstance(operator_symbol, str), operator_symbol
    assert operator_symbol in COMPARISON_OPERATORS, operator_symbol
    operator_type = COMPARISON_OPERATORS[operator_symbol]
    return operator_type(lhs, rhs)


_HEX_PATTERN = r"[a-fA-F0-9]+"


def __map_actions(*mappings: tuple[ParserElement, Callable[[ParseResults], ASTNode]]) -> None:
    """Shorthand for setting `set_parse_action` on ParserElements"""
    for element, action in mappings:
        element.set_parse_action(action)


def __setup_syntax() -> ParserElement:
    # pylint: disable=too-many-locals

    expression = Forward()

    constant = CaselessKeyword("E") | CaselessKeyword("PI")
    number = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")

    variable = Suppress("${") + Regex(VARIABLE_PATTERN) + Suppress("}")

    hex_number = Regex(rf"0x{_HEX_PATTERN}")
    number_from_hex = (
        Suppress(CaselessLiteral("from_hex"))
        + Suppress("(")
        + Regex(rf"(0x)?{_HEX_PATTERN}", flags=RegexFlag.IGNORECASE)
        + Suppress(")")
    )

    variable_as_hex = (
        Suppress(CaselessLiteral("from_hex"))
        + Suppress("(")
        + Optional(Suppress("0x"))
        + Suppress("${")
        + Regex(VARIABLE_PATTERN)
        + Suppress("}")
        + Suppress(")")
    )

    hex_number_handling = hex_number | number_from_hex | variable_as_hex

    addition_operators = one_of(["+", "-"])
    multiplication_operators = one_of(["*", "/", "%"])
    power_operators = one_of(["^"])
    comparison_operators = one_of([">=", "<=", "==", "!=", ">", "<"])

    function_call = (
        Word(alphas, alphanums + "_$")
        + Suppress("(")
        - Optional(DelimitedList(Group(expression)))
        + Suppress(")")
    )
    atomic_expression = addition_operators[...] + (
        (hex_number_handling | function_call | constant | number | variable)
        | Group(Suppress("(") + expression + Suppress(")"))
    )

    power_operation = Forward()
    power_operation <<= atomic_expression + (power_operators + power_operation)[...]

    multiplicative_operation = power_operation + (multiplication_operators + power_operation)[...]

    additive_operation = (
        multiplicative_operation + (addition_operators + multiplicative_operation)[...]
    )

    comparison_operation = additive_operation + (comparison_operators + additive_operation)[...]

    expression <<= comparison_operation

    __map_actions(
        (constant, __build_constant),
        (number, __build_constant),
        (variable, __build_variable),
        (hex_number, __build_constant_from_hex),
        (number_from_hex, __build_constant_from_hex),
        (variable_as_hex, __build_hex_variable),
        (function_call, __build_function_call),
        (atomic_expression, __build_atomic_expression),
        (power_operation, __build_arithmetic_operation),
        (multiplicative_operation, __build_arithmetic_operation),
        (additive_operation, __build_arithmetic_operation),
        (comparison_operation, __build_comparison_operation),
    )
    return expression


__SYNTAX = __setup_syntax()


def parse_expression(expression: str) -> ASTNode:
    """Parse an expression into an abstract syntax tree.

    Parameters
    ----------
    expression : str
        A string containing the expression to be parsed.

    Returns
    -------
    ASTNode
        The root node to of the abstract syntax tree generated from the
        expression passed.

    Raises
    ------
    InvalidSyntaxError
        Raised if the parsed expression can not be parsed.
    UnknownFunctionError
        Raised if an unknown function is raised.
    """
    try:
        root_node = __SYNTAX.parse_string(expression, parse_all=True)[0]
    except (ParseException, ParseSyntaxException) as error:
        raise InvalidSyntaxError("Error raising expression.") from error
    assert isinstance(root_node, ASTNode)
    return root_node
