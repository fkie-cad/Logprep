# pylint: disable=missing-docstring
# pylint: disable=invalid-name
"""
based on https://github.com/pyparsing/pyparsing/blob/master/examples/fourFn.py

Demonstration of the pyparsing module, implementing a simple 4-function expression parser,
with support for scientific notation, and symbols for e and pi.
Extended to add exponentiation and simple built-in functions.
Extended test cases, simplified pushFirst method.
Removed unnecessary expr.suppress() call (thanks Nathaniel Peterson!), and added Group
Changed fnumber to use a Regex, which is now the preferred method
Reformatted to latest pypyparsing features, support multiple and variable args to functions
Copyright 2003-2019 by Paul McGuire
"""

import math
import operator
from abc import ABC, abstractmethod
from enum import Enum, auto
from re import RegexFlag
from typing import Any, Callable, ClassVar, Protocol, Sequence, TypeAlias

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

from logprep.abc.exceptions import LogprepException
from logprep.util.helper import DottedTemplate, FieldValue, get_dotted_field_value


class CalculatorError(LogprepException): ...


class InvalidSyntaxError(CalculatorError): ...


class ParsingError(CalculatorError): ...


class MissingValueError(CalculatorError): ...


class UnknownFunctionError(CalculatorError): ...


class EvaluationError(CalculatorError): ...


class DivisionByZeroError(CalculatorError): ...


# NOTE: The AST emulates its own typing system through enums.


class ValueType(Enum):
    BOOLEAN = auto()
    NUMBER = auto()

    def can_be_cast_to(self, other: "ValueType") -> bool:
        if self == other:
            return True
        if self == ValueType.NUMBER and other == ValueType.BOOLEAN:
            return True
        return False


def parse_value(value: Any, expected_type: ValueType) -> Any:
    match expected_type:
        case ValueType.NUMBER:
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, bool):
                raise ParsingError("Expected number got boolean.")
            if isinstance(value, str):
                if value.upper() == "PI":
                    return math.pi
                if value.upper() == "E":
                    return math.e
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return float(value)
                except (TypeError, ValueError) as error:
                    raise ParsingError(f"Could not parse input {value !r} to number") from error
        case ValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            raise ParsingError(f"Could not parse {value !r}.")
    raise ParsingError(f"Could not parse {value !r} to {expected_type}")


def read_hex_number(value: Any) -> int:
    try:
        return int(value, 16)
    except (ValueError, TypeError) as error:
        raise ParsingError(f"Failed to parse {value !r} as hex_number.") from error


epsilon = 1e-12

fn = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "abs": abs,
    "trunc": int,
    "from_hex": lambda a: int(a, 16),
    "round": round,
    "sgn": lambda a: -1 if a < -epsilon else 1 if a > epsilon else 0,
    # functions with multiple arguments
    "multiply": lambda a, b: a * b,
    "hypot": math.hypot,
    # functions with a variable number of arguments
    "all": lambda *a: all(a),
}


class ASTWalkContext(Protocol):
    def visit(self, node: "ASTNode", *children: "ASTNode") -> None: ...


NodeId: TypeAlias = int
NodeDesc: TypeAlias = str


class DiagramRenderContext(ASTWalkContext):
    def __init__(self):
        self.nodes: dict[NodeId, NodeDesc] = {}
        self.links: list[tuple[NodeId, NodeId]] = []

    def visit(self, node, *children):
        self.nodes[id(node)] = repr(node)
        self.links.extend((id(node), id(child)) for child in children)

    def get_graph_viz(self) -> str:

        def _node_ref(node_id: NodeId) -> str:
            return f"n{node_id}"

        return "\n".join(
            ["digraph {"]
            + [
                f'\t{_node_ref(node_id)} [label="{node_desc}"]'
                for node_id, node_desc in self.nodes.items()
            ]
            + [
                f"\t{_node_ref(parent_id)} -> {_node_ref(child_id)}"
                for parent_id, child_id in self.links
            ]
            + ["}"]
        )


EvaluationContext: TypeAlias = dict[str, FieldValue]


class ASTNode(ABC):
    output_type: ClassVar[ValueType]

    @abstractmethod
    def walk(self, context: ASTWalkContext) -> None: ...

    @abstractmethod
    def evaluate(self, context: EvaluationContext) -> Any: ...

    @property
    @abstractmethod
    def is_constant(self) -> bool: ...

    @property
    @abstractmethod
    def complexity(self) -> int: ...

    @abstractmethod
    def optimize(self) -> "ASTNode": ...

    def get_diagram(self) -> str:
        diagram_render_context = DiagramRenderContext()
        self.walk(diagram_render_context)
        return diagram_render_context.get_graph_viz()


class TerminalASTNode(ASTNode):
    @property
    def complexity(self):
        return 1

    def walk(self, context):
        return context.visit(self)


class ConstantASTNode(TerminalASTNode):

    def __init__(self, value: Any):
        self.value = parse_value(value, self.output_type)

    @property
    def is_constant(self):
        return True

    def __repr__(self):
        return f"<constant {self.value !r}>"

    def evaluate(self, context):
        return self.value

    def optimize(self):
        return type(self)(value=self.value)


class ConstantNumberASTNode(ConstantASTNode):
    output_type = ValueType.NUMBER


class ConstantBooleanASTNode(ConstantASTNode):
    output_type = ValueType.BOOLEAN


class VariableASTNode(TerminalASTNode):
    output_type = ValueType.NUMBER

    def __init__(self, path: str):
        self.path = path

    @property
    def is_constant(self):
        return False

    def _preprocess_field_data(self, value: Any) -> Any:
        return value

    def evaluate(self, context):
        value = get_dotted_field_value(context, self.path)
        if not value:
            raise MissingValueError(f"Missing value for field {self.path!r}.")
        value = self._preprocess_field_data(value)
        return parse_value(value, self.output_type)

    def __repr__(self):
        return f"<variable {self.path !r}>"

    def optimize(self):
        return type(self)(path=self.path)


class HexNumberVariableASTNode(VariableASTNode):
    def _preprocess_field_data(self, value):
        return read_hex_number(value)


class CompositeASTNode(ASTNode):
    input_type: ClassVar[ValueType]

    def __init__(self, *children: ASTNode):
        if not all(child.output_type.can_be_cast_to(self.input_type) for child in children):
            raise InvalidSyntaxError(f"Can not parse all inputs to {self.input_type}.")

        self.children = children

    @property
    def complexity(self):
        return sum(child.complexity for child in self.children) + 1

    @property
    def is_constant(self):
        return all(child.is_constant for child in self.children)

    def walk(self, context):
        context.visit(self, *self.children)
        for child in self.children:
            child.walk(context)


class NegateASTNode(CompositeASTNode):
    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    def __init__(self, inner: ASTNode):
        super().__init__(inner)
        self.inner = inner

    def optimize(self):
        optimized_inner = self.inner.optimize()
        if optimized_inner.is_constant:
            return ConstantNumberASTNode(-optimized_inner.evaluate({}))
        return NegateASTNode(optimized_inner)

    def evaluate(self, context):
        return -self.inner.evaluate(context)

    def __repr__(self) -> str:
        return "<negate>"


class OperationASTNode(CompositeASTNode):
    operator_symbol: ClassVar[str]
    # NOTE: decided against handling the typing by designing the ASTNode class
    # generic. During construction of the AST the typing is dynamic
    # only the constructed is then checked for typing.
    operation_fn: ClassVar[Callable[[Any, Any], Any]]

    def __init__(
        self,
        lhs: ASTNode,
        rhs: ASTNode,
    ):
        super().__init__(lhs, rhs)
        self.lhs = lhs
        self.rhs = rhs

    def _operation_specific_optimizations(self, lhs: ASTNode, rhs: ASTNode) -> ASTNode | None:
        return None

    def optimize(self):
        lhs_optimized = self.lhs.optimize()
        rhs_optimized = self.rhs.optimize()

        if lhs_optimized.is_constant and rhs_optimized.is_constant:
            return ConstantNumberASTNode(
                self.operation_fn(
                    lhs_optimized.evaluate({}),
                    rhs_optimized.evaluate({}),
                )
            )
        if specific_optimization := self._operation_specific_optimizations(
            lhs_optimized, rhs_optimized
        ):
            return specific_optimization

        return type(self)(lhs_optimized, rhs_optimized)

    def evaluate(self, context):
        return self.operation_fn(
            self.lhs.evaluate(context),
            self.rhs.evaluate(context),
        )

    def __repr__(self) -> str:
        return f"<op {self.operator_symbol}>"


class ArithmeticASTNode(OperationASTNode):
    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    @abstractmethod
    def _operation_specific_optimizations(self, lhs: ASTNode, rhs: ASTNode) -> ASTNode | None: ...

    def optimize(self):
        lhs_optimized = self.lhs.optimize()
        rhs_optimized = self.rhs.optimize()

        if lhs_optimized.is_constant and rhs_optimized.is_constant:
            try:
                return ConstantNumberASTNode(
                    self.operation_fn(
                        lhs_optimized.evaluate({}),
                        rhs_optimized.evaluate({}),
                    )
                )
            except ZeroDivisionError as error:
                raise DivisionByZeroError("Zero division error on optimization") from error
        if specific_optimization := self._operation_specific_optimizations(
            lhs_optimized, rhs_optimized
        ):
            return specific_optimization

        return type(self)(lhs_optimized, rhs_optimized)

    def evaluate(self, context):
        try:
            return super().evaluate(context)
        except ZeroDivisionError as error:
            # division and power operator might run into ZeroDevisionErrors
            # we want to repack those into a class inheriting from LogprepException
            raise DivisionByZeroError("Division by zero.") from error


def _is_constant_value(node: ASTNode, value: int) -> bool:
    return node.is_constant and node.evaluate({}) == value


class AddASTNode(ArithmeticASTNode):
    operator_symbol = "+"
    operation_fn = operator.add

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            return lhs
        if _is_constant_value(lhs, 0):
            return rhs
        return None


class SubASTNode(ArithmeticASTNode):
    operator_symbol = "-"
    operation_fn = operator.sub

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            return lhs
        if _is_constant_value(lhs, 0):
            return NegateASTNode(rhs).optimize()
        return None


class MulASTNode(ArithmeticASTNode):
    operator_symbol = "*"
    operation_fn = operator.mul

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0) or _is_constant_value(lhs, 0):
            return ConstantNumberASTNode(0)
        if _is_constant_value(rhs, 1):
            return lhs
        if _is_constant_value(lhs, 1):
            return rhs
        return None


class DivASTNode(ArithmeticASTNode):
    operator_symbol = "/"
    operation_fn = operator.truediv

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            raise DivisionByZeroError("Expression resulted to a division by zero on optimization.")
        if _is_constant_value(rhs, 1):
            return lhs
        return None


class PowASTNode(ArithmeticASTNode):
    operator_symbol = "^"
    operation_fn = operator.pow

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            return ConstantNumberASTNode(1)
        if _is_constant_value(rhs, 1):
            return lhs
        if _is_constant_value(lhs, 1):
            return ConstantNumberASTNode(1)
        return None


class ComparisonASTNode(OperationASTNode):
    input_type = ValueType.NUMBER
    output_type = ValueType.BOOLEAN

    def optimize(self):
        if not all(child.is_constant for child in self.children):
            return type(self)(
                self.lhs,
                self.rhs,
            )
        return ConstantBooleanASTNode(self.evaluate({}))


class EqualASTNode(ComparisonASTNode):
    operator_symbol = "=="
    operation_fn = operator.eq


class UnequalASTNode(ComparisonASTNode):
    operator_symbol = "!="
    operation_fn = operator.ne


class LessThanASTNode(ComparisonASTNode):
    operator_symbol = "<"
    operation_fn = operator.lt


class LessOrEqualThanASTNode(ComparisonASTNode):
    operator_symbol = "<="
    operation_fn = operator.le


class GreaterThanASTNode(ComparisonASTNode):
    operator_symbol = ">"
    operation_fn = operator.gt


class GreaterOrEqualThanASTNode(ComparisonASTNode):
    operator_symbol = ">="
    operation_fn = operator.ge


class RangeCheckASTNode(CompositeASTNode):
    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    def __init__(
        self,
        lower_bound: ASTNode,
        lower_bound_is_inclusive: bool,
        value: ASTNode,
        upper_bound: ASTNode,
        upper_bound_is_inclusive: bool,
    ):
        super().__init__(lower_bound, value, upper_bound)
        self.lower_bound = lower_bound
        self.lower_bound_is_inclusive = lower_bound_is_inclusive
        self.value = value
        self.upper_bound = upper_bound
        self.upper_bound_is_inclusive = upper_bound_is_inclusive

    def optimize(self):
        if self.is_constant:
            return ConstantBooleanASTNode(self.evaluate({}))
        return type(self)(
            self.lower_bound,
            self.lower_bound_is_inclusive,
            self.value,
            self.upper_bound,
            self.upper_bound_is_inclusive,
        )

    def evaluate(self, context):
        value = self.value.evaluate(context)
        lower_bound = self.lower_bound.evaluate(context)
        op = operator.le if self.lower_bound_is_inclusive else operator.lt
        if not op(lower_bound, value):
            return False
        upper_bound = self.upper_bound.evaluate(context)
        op = operator.le if self.upper_bound_is_inclusive else operator.lt
        return op(value, upper_bound)


ARITHMETIC_OPERATORS = {
    op.operator_symbol: op
    for op in (
        AddASTNode,
        SubASTNode,
        MulASTNode,
        DivASTNode,
        PowASTNode,
    )
}

COMPARISON_OPERATORS = {
    op.operator_symbol: op
    for op in (
        EqualASTNode,
        UnequalASTNode,
        LessThanASTNode,
        LessOrEqualThanASTNode,
        GreaterThanASTNode,
        GreaterOrEqualThanASTNode,
    )
}


class FunctionCallASTNode(CompositeASTNode):
    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    # TODO: make all a special case
    def __init__(
        self, function_name: str, function_call: Callable[..., Any], children: Sequence[ASTNode]
    ):
        super().__init__(*children)
        self.function_name = function_name
        self.function_call = function_call

    @property
    def complexity(self):
        return sum(child.complexity for child in self.children)

    @property
    def is_constant(self):
        return all(child.is_constant for child in self.children)

    def optimize(self) -> ASTNode:
        optimized_clone = FunctionCallASTNode(
            function_name=self.function_name,
            function_call=self.function_call,
            children=[child.optimize() for child in self.children],
        )
        if not all(child.is_constant for child in optimized_clone.children):
            return optimized_clone

        try:
            my_static_value = optimized_clone.evaluate({})
            return ConstantNumberASTNode(value=my_static_value)
        except CalculatorError as error:
            # As every child considered consider itself constant
            # evaluating with an empty context should not raise
            # an MissingValueError. All other errors should already
            # be detected at compile time.

            # If the following assert is hit one of the children
            # is probably wrong about itself being constant.
            assert not error, self.children

            # Returning the optimized_clone if asserts are disabled
            # as this is probably preferable to failing on optimization.
            return optimized_clone

    def walk(self, context):
        context.visit(self, *self.children)
        for child in self.children:
            child.walk(context)

    def evaluate(self, context):
        operands = [child.evaluate(context) for child in self.children]
        if any(isinstance(operand, bool) for operand in operands):
            raise ValueError("boolean values cannot be used as operands")

        operands = [child.evaluate(context) for child in self.children]
        try:
            return self.function_call(*operands)
        except Exception as error:
            raise EvaluationError(
                f"Failed on operator {self.function_name !r} with values {operands !r}"
            ) from error

    def __repr__(self):
        return f"<op {self.function_name !r}>"


def build_constant(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return ConstantNumberASTNode(x[0])


def build_constant_from_hex(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    hex_number = read_hex_number(x[0])
    return ConstantNumberASTNode(hex_number)


def build_variable(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return VariableASTNode(x[0])


def build_hex_variable(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return HexNumberVariableASTNode(x[0])


def build_atom(x):
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


def build_fn(x):
    if len(x) == 1:
        assert isinstance(x[0], ASTNode)
        return x[0]
    assert len(x) >= 1, x
    function_name = x[0]
    assert isinstance(function_name, str)
    if function_name not in fn:
        raise UnknownFunctionError(f"Unknown function {function_name !r}.")
    assert all(
        isinstance(i, ParseResults) and len(i) == 1 and isinstance(i[0], ASTNode) for i in x[1:]
    )

    return FunctionCallASTNode(
        function_name,
        fn[function_name],
        [i[0] for i in x[1:]],
    )


def build_arithmetic_operation(x):
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


def build_comparison_operation(x):
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


def setup_bnf() -> ParserElement:
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
    e.set_parse_action(build_constant)

    pi = CaselessKeyword("PI")
    pi.set_parse_action(build_constant)
    # fnumber = Combine(Word("+-"+nums, nums) +
    #                    Optional("." + Optional(Word(nums))) +
    #                    Optional(e + Word("+-"+nums, nums)))
    # or use provided pyparsing_common.number, but convert back to str:
    # fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
    fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
    fnumber.set_parse_action(build_constant)
    variable = Suppress("${") + Regex(DottedTemplate.braceidpattern) + Suppress("}")
    variable.set_parse_action(build_variable)

    hex_number = Regex(r"0x[0-9a-f]")
    number_from_hex = (
        Suppress("from_hex")
        + Suppress("(")
        + Regex(r"(0x)?[a-f0-9]+", flags=RegexFlag.IGNORECASE)
        + Suppress(")")
    )
    hex_number.set_parse_action(build_constant_from_hex)
    number_from_hex.set_parse_action(build_constant_from_hex)

    variable_as_hex = (
        Suppress("from_hex")
        + Suppress("(")
        + Optional(Suppress("0x"))
        + Suppress("${")
        + Regex(DottedTemplate.braceidpattern)
        + Suppress("}")
        + Suppress(")")
    )
    variable_as_hex.set_parse_action(build_hex_variable)

    hex_number_handling = hex_number | number_from_hex | variable_as_hex

    ident = Word(alphas, alphanums + "_$")
    plus, minus, mult, div = map(Literal, "+-*/")
    lpar, rpar = map(Suppress, "()")
    addop = plus | minus
    multop = mult | div
    expop = Literal("^")
    comparisonop = one_of(">= <= == != > <")

    expr_list = DelimitedList(Group(bnf))

    fn_call = ident + lpar - expr_list + rpar
    fn_call.set_parse_action(build_fn)
    atom = addop[...] + (
        (hex_number_handling | fn_call | pi | e | fnumber | ident | variable)
        | Group(lpar + bnf + rpar)
    )
    atom.set_parse_action(build_atom)
    # A Forward declaration is required because the power expression recursively
    # references itself on the right-hand side of the exponent operator.
    # By defining exponentiation as "atom [ ^ power_expression ]..." instead of
    # "atom [ ^ atom ]...", exponents are evaluated from right to left:
    # 2^3^2 = 2^(3^2), not (2^3)^2.
    power_expr = Forward()
    power_expr <<= atom + (expop + power_expr)[...]
    power_expr.add_parse_action(build_arithmetic_operation)

    multiplicative_expr = power_expr + (multop + power_expr)[...]
    multiplicative_expr.add_parse_action(build_arithmetic_operation)

    additive_expr = multiplicative_expr + (addop + multiplicative_expr)[...]
    additive_expr.add_parse_action(build_arithmetic_operation)

    # Optional allows at most one comparison; chained comparisons are not supported.
    comparison_expr = additive_expr + (comparisonop + additive_expr)[...]
    comparison_expr.add_parse_action(build_comparison_operation)

    bnf <<= comparison_expr

    return bnf


_BNF = setup_bnf()


def compile_expression(expression: str) -> ASTNode:
    try:
        root_node = _BNF.parse_string(expression, parse_all=True)[0]
    except (ParseException, ParseSyntaxException) as error:
        raise InvalidSyntaxError("Error raising expression.") from error
    assert isinstance(root_node, ASTNode)
    return root_node


class BNF(Forward):
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

    exprStack: list

    # use CaselessKeyword for e and pi, to avoid accidentally matching
    # functions that start with 'e' or 'pi' (such as 'exp'); Keyword
    # and CaselessKeyword only match whole words
    e = CaselessKeyword("E")
    pi = CaselessKeyword("PI")
    # fnumber = Combine(Word("+-"+nums, nums) +
    #                    Optional("." + Optional(Word(nums))) +
    #                    Optional(e + Word("+-"+nums, nums)))
    # or use provided pyparsing_common.number, but convert back to str:
    # fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
    fnumber = Regex(r"[+-]?[a-zA-Z0-9]+(?:\.\d*)?(?:[eE][+-]?\d+)?")

    ident = Word(alphas, alphanums + "_$")

    plus, minus, mult, div = map(Literal, "+-*/")
    lpar, rpar = map(Suppress, "()")
    addop = plus | minus
    multop = mult | div
    expop = Literal("^")
    comparisonop = one_of(">= <= == != > <")

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(BNF, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        super().__init__()
        self.exprStack = []
        expr_list = DelimitedList(Group(self))

        # add parse action that replaces the function identifier with a (name, number of args) tuple
        def insert_fn_argcount_tuple(t):
            _fn = t.pop(0)
            num_args = len(t[0])
            t.insert(0, (_fn, num_args))

        fn_call = (self.ident + self.lpar - Group(expr_list) + self.rpar).set_parse_action(
            insert_fn_argcount_tuple
        )
        atom = (
            self.addop[...]
            + (
                (fn_call | self.pi | self.e | self.fnumber | self.ident).set_parse_action(
                    self.push_first
                )
                | Group(self.lpar + self + self.rpar)
            )
        ).set_parse_action(self.push_unary_minus)

        # A Forward declaration is required because the power expression recursively
        # references itself on the right-hand side of the exponent operator.
        # By defining exponentiation as "atom [ ^ power_expression ]..." instead of
        # "atom [ ^ atom ]...", exponents are evaluated from right to left:
        # 2^3^2 = 2^(3^2), not (2^3)^2.
        power_expr = Forward()
        power_expr <<= atom + (self.expop + power_expr).set_parse_action(self.push_first)[...]

        multiplicative_expr = (
            power_expr + (self.multop + power_expr).set_parse_action(self.push_first)[...]
        )
        additive_expr = (
            multiplicative_expr
            + (self.addop + multiplicative_expr).set_parse_action(self.push_first)[...]
        )

        # Optional allows at most one comparison; chained comparisons are not supported.
        comparison_expr = additive_expr + Optional(
            (self.comparisonop + additive_expr).set_parse_action(self.push_first)
        )

        forward_self: Forward = self  # narrow the type for mypy before using Forward.__ilshift__
        forward_self <<= comparison_expr

    def push_first(self, toks):
        self.exprStack.append(toks[0])

    def push_unary_minus(self, toks):
        for t in toks:
            if t == "-":
                self.exprStack.append("unary -")
            else:
                break

    @staticmethod
    def reject_boolean_operands(*operands):
        if any(isinstance(operand, bool) for operand in operands):
            raise ValueError("boolean values cannot be used as operands")

    def evaluate_stack(self):
        op, num_args = self.exprStack.pop(), 0
        if isinstance(op, tuple):
            op, num_args = op
        if op == "unary -":
            operand = self.evaluate_stack()
            self.reject_boolean_operands(operand)
            return -operand
        if op in opn:
            # Operands are pushed onto the stack in reverse order
            op2 = self.evaluate_stack()
            op1 = self.evaluate_stack()
            self.reject_boolean_operands(op1, op2)
            return opn[op](op1, op2)
        if op == "PI":
            return math.pi  # 3.1415926535
        if op == "E":
            return math.e  # 2.718281828
        if op in fn:
            # note: args are pushed onto the stack in reverse order
            args = reversed([self.evaluate_stack() for _ in range(num_args)])
            return fn[op](*args)
        if op[0].isalpha():
            raise ValueError(f"invalid identifier '{op}'")
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            try:
                return float(op)
            except ValueError:
                return op
