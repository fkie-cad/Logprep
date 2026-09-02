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


def _build_constant(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return ConstantNumberASTNode(x[0])


def _build_constant_from_hex(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    hex_number = read_hex_number(x[0])
    return ConstantNumberASTNode(hex_number)


def _build_variable(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return VariableASTNode(x[0])


def _build_hex_variable(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return HexNumberVariableASTNode(x[0])


def _build_atom(x):
    if len(x) == 1:
        if isinstance(x[0], ASTNode):
            return x[0]
        assert isinstance(x[0], ParseResults)
        assert len(x[0]) == 1 and isinstance(x[0][0], ASTNode)
        return x[0][0]
    assert len(x) >= 2
    signs = x[:-1]
    assert all(sign in ("+", "-") for sign in signs), signs
    node = x[-1]
    if isinstance(node, ParseResults):
        assert len(node) == 1
        node = node[0]
    assert isinstance(node, ASTNode)
    if len([s for s in signs if s == "-"]) % 2 == 1:
        return NegateASTNode(node)
    return node


def _build_fn(x):
    if len(x) == 1:
        assert isinstance(x[0], ASTNode)
        return x[0]
    assert len(x) >= 1, x
    function_name = x[0]
    assert isinstance(function_name, str)
    assert all(isinstance(i, ParseResults) and len(i) == 1 for i in x[1:])
    params = [i[0] for i in x[1:]]
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


def _build_arithmetic_operation(x):
    assert len(x) > 0 and len(x) % 2 == 1

    lhs = x[0]
    assert isinstance(lhs, ASTNode)

    for i in range(1, len(x), 2):
        operator_symbol, rhs = x[i], x[i + 1]
        assert isinstance(operator_symbol, str)
        assert isinstance(rhs, ASTNode)
        assert operator_symbol in ARITHMETIC_OPERATORS
        operator_type = ARITHMETIC_OPERATORS[operator_symbol]
        lhs = operator_type(lhs, rhs)
    return lhs


def _build_comparison_operation(x):
    if len(x) == 1:
        assert isinstance(x[0], ASTNode)
        return x[0]

    if len(x) > 5:
        raise InvalidSyntaxError("Comparisons can not be chained.")

    if len(x) == 5:
        lower_bound = x[0]
        lower_op = x[1]
        value = x[2]
        upper_op = x[3]
        upper_bound = x[4]
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

    if len(x) != 3:
        raise InvalidSyntaxError("Comparisons needs two operands.")

    lhs = x[0]
    operator_symbol = x[1]
    rhs = x[2]
    assert isinstance(lhs, ASTNode)
    assert isinstance(operator_symbol, str)
    assert isinstance(rhs, ASTNode)
    assert operator_symbol in COMPARISON_OPERATORS
    operator_type = COMPARISON_OPERATORS[operator_symbol]
    return operator_type(lhs, rhs)


def _setup_bnf() -> ParserElement:
    """
    expop                 :: '^'
    multop                :: '*' | '/'
    addop                 :: '+' | '-'
    comparisonop          :: '>' | '<' | '>=' | '<=' | '==' | '!='
    integer               :: ['+' | '-'] '0'..'9'+
    atom                  :: PI | E | real | fn '(' comparison_expr ')' | '(' comparison_expr ')'
    power_expr            :: atom [expop power_expr]*
    multiplicative_expr   :: power_expr [multop power_expr]*
    additive_expr         :: multiplicative_expr [addop multiplicative_expr]*
    comparison_expr       :: additive_expr [comparisonop additive_expr]
    """

    bnf = Forward()

    # use CaselessKeyword for e and pi, to avoid accidentally matching
    # functions that start with 'e' or 'pi' (such as 'exp'); Keyword
    # and CaselessKeyword only match whole words
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
    # A Forward declaration is required because the power expression recursively
    # references itself on the right-hand side of the exponent operator.
    # By defining exponentiation as "atom [ ^ power_expression ]..." instead of
    # "atom [ ^ atom ]...", exponents are evaluated from right to left:
    # 2^3^2 = 2^(3^2), not (2^3)^2.
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
