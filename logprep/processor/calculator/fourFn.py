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

import abc
import math
import operator
from typing import Any, Protocol, Sequence, TypeAlias

from pyparsing import (
    CaselessKeyword,
    DelimitedList,
    Forward,
    Group,
    Literal,
    Optional,
    ParserElement,
    ParseResults,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    one_of,
)

epsilon = 1e-12
# map operator symbols to corresponding arithmetic and comparison operations.
opn = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

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


class ASTDescriptionContext(Protocol):
    def describe(self, node: "ASTNode", *children: "ASTNode") -> None: ...


NodeId: TypeAlias = int
NodeDesc: TypeAlias = str


class GraphVizGenerator(ASTDescriptionContext):
    def __init__(self):
        self.nodes: dict[NodeId, NodeDesc] = {}
        self.links: list[tuple[NodeId, NodeId]] = []

    def describe(self, node, *children):
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


class ASTNode(abc.ABC):
    def write_description(self, context: ASTDescriptionContext) -> None: ...

    def evaluate(self) -> Any: ...


class TerminalASTNode(ASTNode):
    def __init__(self, value: str):
        self.value = value

    def write_description(self, context):
        return context.describe(self)

    def __repr__(self):
        return f"<value {self.value !r}>"

    def evaluate(self):
        if self.value == "PI":
            return math.pi  # 3.1415926535
        if self.value == "E":
            return math.e  # 2.718281828
        # try to evaluate as int first, then as float if int fails
        try:
            return int(self.value)
        except ValueError:
            try:
                return float(self.value)
            except ValueError:
                return self.value


class CompositeASTNode(ASTNode):
    def __init__(self, operation: str, children: Sequence[ASTNode]):
        self.operation = operation
        self.children = children

    def write_description(self, context):
        context.describe(self, *self.children)
        for child in self.children:
            child.write_description(context)

    def evaluate(self):
        if self.operation == "unary -":
            assert len(self.children) == 1
            return -self.children[0].evaluate()

        op = opn.get(self.operation) or fn.get(self.operation)
        if not op:
            raise Exception(f"unkown op {self.operation !r}")
        operands = [child.evaluate() for child in self.children]

        if any(isinstance(operand, bool) for operand in operands):
            raise ValueError("boolean values cannot be used as operands")
        return op(*operands)

    def __repr__(self):
        return f"<op {self.operation !r}>"


def build_terminal(x):
    assert len(x) == 1
    assert isinstance(x[0], str)
    return TerminalASTNode(x[0])


def build_atom(x):
    if len(x) == 1:
        if isinstance(x[0], ASTNode):
            return x[0]
        assert isinstance(x[0], ParseResults)
        assert len(x[0]) == 1 and isinstance(x[0][0], ASTNode)
        return x[0][0]
    assert len(x) == 2
    assert x[0] in ("+", "-"), x
    assert isinstance(x[1], ASTNode)
    if x[0] == "-":
        return CompositeASTNode("unary -", [x[1]])
    return x[1]


def build_fn(x):
    if len(x) == 1:
        assert isinstance(x[0], ASTNode)
        return x[0]
    assert len(x) >= 1, x
    assert isinstance(x[0], str)
    assert all(
        isinstance(i, ParseResults) and len(i) == 1 and isinstance(i[0], ASTNode) for i in x[1:]
    )
    return CompositeASTNode(x[0], [i[0] for i in x[1:]])


def build_op(x):
    assert len(x) > 0 and len(x) % 2 == 1
    assert isinstance(x[0], ASTNode)
    op = x[0]
    for i in range(1, len(x), 2):
        assert isinstance(x[i], str)
        assert isinstance(x[i + 1], ASTNode)
        op = CompositeASTNode(x[i], [op, x[i + 1]])
    return op


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
    e.set_parse_action(build_terminal)

    pi = CaselessKeyword("PI")
    pi.set_parse_action(build_terminal)
    # fnumber = Combine(Word("+-"+nums, nums) +
    #                    Optional("." + Optional(Word(nums))) +
    #                    Optional(e + Word("+-"+nums, nums)))
    # or use provided pyparsing_common.number, but convert back to str:
    # fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
    fnumber = Regex(r"[+-]?[a-zA-Z0-9]+(?:\.\d*)?(?:[eE][+-]?\d+)?")
    fnumber.set_parse_action(build_terminal)
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
    atom = addop[...] + ((fn_call | pi | e | fnumber | ident) | Group(lpar + bnf + rpar))
    atom.set_parse_action(build_atom)
    # A Forward declaration is required because the power expression recursively
    # references itself on the right-hand side of the exponent operator.
    # By defining exponentiation as "atom [ ^ power_expression ]..." instead of
    # "atom [ ^ atom ]...", exponents are evaluated from right to left:
    # 2^3^2 = 2^(3^2), not (2^3)^2.
    power_expr = Forward()
    power_expr <<= atom + (expop + power_expr)[...]
    power_expr.add_parse_action(build_op)

    multiplicative_expr = power_expr + (multop + power_expr)[...]
    multiplicative_expr.add_parse_action(build_op)

    additive_expr = multiplicative_expr + (addop + multiplicative_expr)[...]
    additive_expr.add_parse_action(build_op)

    # Optional allows at most one comparison; chained comparisons are not supported.
    comparison_expr = additive_expr + Optional(comparisonop + additive_expr)
    comparison_expr.add_parse_action(build_op)

    bnf <<= comparison_expr

    return bnf


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
