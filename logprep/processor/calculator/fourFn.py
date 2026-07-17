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

from pyparsing import (
    CaselessKeyword,
    DelimitedList,
    Forward,
    Group,
    Literal,
    Optional,
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
        expr_list = DelimitedList(Group(self))  # pylint: disable=E1121

        # add parse action that replaces the function identifier with a (name, number of args) tuple
        def insert_fn_argcount_tuple(t):
            fn = t.pop(0)  # pylint: disable=redefined-outer-name
            num_args = len(t[0])
            t.insert(0, (fn, num_args))

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
            raise Exception(  # pylint: disable=broad-exception-raised
                "boolean values cannot be used as operands"
            )

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
            raise Exception(f"invalid identifier '{op}'")  # pylint: disable=broad-exception-raised
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            try:
                return float(op)
            except ValueError:
                return op
