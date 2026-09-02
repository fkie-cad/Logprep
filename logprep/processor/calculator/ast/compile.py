# pylint: disable=missing-docstring
# pylint: disable=invalid-name
from re import RegexFlag

from pyparsing import (
    CaselessKeyword,
    DelimitedList,
    Forward,
    Group,
    Literal,
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

from logprep.processor.calculator.ast.exceptions import InvalidSyntaxError
from logprep.processor.calculator.ast.node import (
    ARITHMETIC_OPERATORS,
    COMPARISON_OPERATORS,
    AllFunctionASTNode,
    AnyFunctionASTNode,
    ASTNode,
    ConstantNumberASTNode,
    HexNumberVariableASTNode,
    NegateASTNode,
    NumericFunctionCallASTNode,
    RangeCheckASTNode,
    UnknownFunctionError,
    VariableASTNode,
)
from logprep.processor.calculator.ast.util import read_hex_number
from logprep.util.helper import DottedTemplate


def _build_constant(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1
    assert isinstance(parsed[0], str)
    return ConstantNumberASTNode(parsed[0])


def _build_constant_from_hex(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1
    assert isinstance(parsed[0], str)
    hex_number = read_hex_number(parsed[0])
    return ConstantNumberASTNode(hex_number)


def _build_variable(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1
    assert isinstance(parsed[0], str)
    return VariableASTNode(parsed[0])


def _build_hex_variable(parsed: ParseResults) -> ASTNode:
    assert len(parsed) == 1
    assert isinstance(parsed[0], str)
    return HexNumberVariableASTNode(parsed[0])


def _build_atom(parsed: ParseResults) -> ASTNode:
    if len(parsed) == 1:
        if isinstance(parsed[0], ASTNode):
            return parsed[0]
        assert isinstance(parsed[0], ParseResults)
        assert len(parsed[0]) == 1 and isinstance(parsed[0][0], ASTNode)
        return parsed[0][0]
    assert len(parsed) >= 2
    signs = parsed[:-1]
    assert all(sign in ("+", "-") for sign in signs), signs
    node = parsed[-1]
    if isinstance(node, ParseResults):
        assert len(node) == 1
        node = node[0]
    assert isinstance(node, ASTNode)
    if len([s for s in signs if s == "-"]) % 2 == 1:
        return NegateASTNode(node)
    return node


def _build_fn(parsed: ParseResults) -> ASTNode:
    if len(parsed) == 1:
        assert isinstance(parsed[0], ASTNode)
        return parsed[0]
    assert len(parsed) >= 1, parsed
    function_name = parsed[0]
    assert isinstance(function_name, str)
    assert all(isinstance(i, ParseResults) and len(i) == 1 for i in parsed[1:])
    params = [i[0] for i in parsed[1:]]
    assert all(isinstance(param, ASTNode) for param in params)
    if function_name == "all":
        return AllFunctionASTNode(*params)
    if function_name == "any":
        return AnyFunctionASTNode(*params)

    if not NumericFunctionCallASTNode.implements(function_name):
        raise UnknownFunctionError(f"Unknown function {function_name !r}.")

    return NumericFunctionCallASTNode(
        function_name,
        params,
    )


def _build_arithmetic_operation(parsed: ParseResults) -> ASTNode:
    assert len(parsed) > 0 and len(parsed) % 2 == 1

    lhs = parsed[0]
    assert isinstance(lhs, ASTNode)

    for i in range(1, len(parsed), 2):
        operator_symbol, rhs = parsed[i], parsed[i + 1]
        assert isinstance(operator_symbol, str)
        assert isinstance(rhs, ASTNode)
        assert operator_symbol in ARITHMETIC_OPERATORS
        operator_type = ARITHMETIC_OPERATORS[operator_symbol]
        lhs = operator_type(lhs, rhs)
    return lhs


def _build_comparison_operation(parsed: ParseResults) -> ASTNode:
    if len(parsed) == 1:
        assert isinstance(parsed[0], ASTNode)
        return parsed[0]

    if len(parsed) > 5:
        raise InvalidSyntaxError("Comparisons can not be chained.")

    if len(parsed) == 5:
        lower_bound = parsed[0]
        lower_op = parsed[1]
        value = parsed[2]
        upper_op = parsed[3]
        upper_bound = parsed[4]
        assert isinstance(lower_bound, ASTNode)
        assert isinstance(lower_op, str)
        assert isinstance(value, ASTNode)
        assert isinstance(upper_op, str)
        assert isinstance(upper_bound, ASTNode)
        if not all(op in ("<", "<=") for op in (lower_op, upper_op)):
            raise InvalidSyntaxError(
                f"Range check required comparison to be '<' or '<=' got {lower_op !r} and {upper_op !r}."
            )
        return RangeCheckASTNode(
            lower_bound,
            lower_op == "<=",
            value,
            upper_bound,
            upper_op == "<=",
        )

    if len(parsed) != 3:
        raise InvalidSyntaxError("Comparisons needs two operands.")

    lhs = parsed[0]
    operator_symbol = parsed[1]
    rhs = parsed[2]
    assert isinstance(lhs, ASTNode)
    assert isinstance(operator_symbol, str)
    assert isinstance(rhs, ASTNode)
    assert operator_symbol in COMPARISON_OPERATORS
    operator_type = COMPARISON_OPERATORS[operator_symbol]
    return operator_type(lhs, rhs)


def _setup_bnf() -> ParserElement:
    bnf = Forward()

    e = CaselessKeyword("E")
    e.set_parse_action(_build_constant)

    pi = CaselessKeyword("PI")
    pi.set_parse_action(_build_constant)

    number = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
    number.set_parse_action(_build_constant)

    variable = Suppress("${") + Regex(DottedTemplate.braceidpattern) + Suppress("}")
    variable.set_parse_action(_build_variable)

    hex_number = Regex(r"0x[0-9a-f]")
    number_from_hex = (
        Suppress("from_hex")
        + Suppress("(")
        + Regex(r"(0x)?[a-f0-9]+", flags=RegexFlag.IGNORECASE)
        + Suppress(")")
    )
    hex_number.set_parse_action(_build_constant_from_hex)
    number_from_hex.set_parse_action(_build_constant_from_hex)

    variable_as_hex = (
        Suppress("from_hex")
        + Suppress("(")
        + Optional(Suppress("0x"))
        + Suppress("${")
        + Regex(DottedTemplate.braceidpattern)
        + Suppress("}")
        + Suppress(")")
    )
    variable_as_hex.set_parse_action(_build_hex_variable)

    hex_number_handling = hex_number | number_from_hex | variable_as_hex

    ident = Word(alphas, alphanums + "_$")
    plus, minus, mult, div, mod = map(Literal, "+-*/%")
    lpar, rpar = map(Suppress, "()")
    addop = plus | minus
    multop = mult | div | mod
    expop = Literal("^")
    comparisonop = one_of(">= <= == != > <")

    expr_list = DelimitedList(Group(bnf))

    fn_call = ident + lpar - expr_list + rpar
    fn_call.set_parse_action(_build_fn)
    atom = addop[...] + (
        (hex_number_handling | fn_call | pi | e | number | ident | variable)
        | Group(lpar + bnf + rpar)
    )
    atom.set_parse_action(_build_atom)

    power_expr = Forward()
    power_expr <<= atom + (expop + power_expr)[...]
    power_expr.add_parse_action(_build_arithmetic_operation)

    multiplicative_expr = power_expr + (multop + power_expr)[...]
    multiplicative_expr.add_parse_action(_build_arithmetic_operation)

    additive_expr = multiplicative_expr + (addop + multiplicative_expr)[...]
    additive_expr.add_parse_action(_build_arithmetic_operation)

    comparison_expr = additive_expr + (comparisonop + additive_expr)[...]
    comparison_expr.add_parse_action(_build_comparison_operation)

    bnf <<= comparison_expr

    return bnf


_BNF = _setup_bnf()


def compile_expression(expression: str) -> ASTNode:
    try:
        root_node = _BNF.parse_string(expression, parse_all=True)[0]
    except (ParseException, ParseSyntaxException) as error:
        raise InvalidSyntaxError("Error raising expression.") from error
    assert isinstance(root_node, ASTNode)
    return root_node
