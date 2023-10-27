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
    Forward,
    Group,
    Literal,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    delimitedList,
)

epsilon = 1e-12
# map operator symbols to corresponding arithmetic operations
opn = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
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
    # functionsl with multiple arguments
    "multiply": lambda a, b: a * b,
    "hypot": math.hypot,
    # functions with a variable number of arguments
    "all": lambda *a: all(a),
}


class BNF(Forward):
    """
    expop   :: '^'
    multop  :: '*' | '/'
    addop   :: '+' | '-'
    integer :: ['+' | '-'] '0'..'9'+
    atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
    factor  :: atom [ expop factor ]*
    term    :: factor [ multop factor ]*
    expr    :: term [ addop term ]*
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

    def push_first(self, toks):
        self.exprStack.append(toks[0])

    def push_unary_minus(self, toks):
        for t in toks:
            if t == "-":
                self.exprStack.append("unary -")
            else:
                break

    def evaluate_stack(self):
        op, num_args = self.exprStack.pop(), 0
        if isinstance(op, tuple):
            op, num_args = op
        if op == "unary -":
            return -self.evaluate_stack()
        if op in "+-*/^":
            # note: operands are pushed onto the stack in reverse order
            op2 = self.evaluate_stack()
            op1 = self.evaluate_stack()
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

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(BNF, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        super().__init__()
        self.exprStack = []
        expr_list = delimitedList(Group(self))  # pylint: disable=E1121

        # add parse action that replaces the function identifier with a (name, number of args) tuple
        def insert_fn_argcount_tuple(t):
            fn = t.pop(0)  # pylint: disable=redefined-outer-name
            num_args = len(t[0])
            t.insert(0, (fn, num_args))

        fn_call = (self.ident + self.lpar - Group(expr_list) + self.rpar).setParseAction(
            insert_fn_argcount_tuple
        )
        atom = (
            self.addop[...]
            + (
                (fn_call | self.pi | self.e | self.fnumber | self.ident).setParseAction(
                    self.push_first
                )
                | Group(self.lpar + self + self.rpar)
            )
        ).setParseAction(self.push_unary_minus)

        # by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...",
        # we get right-to-left exponents,
        # instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = Forward()
        factor <<= atom + (self.expop + factor).setParseAction(self.push_first)[...]
        term = factor + (self.multop + factor).setParseAction(self.push_first)[...]
        self <<= term + (self.addop + term).setParseAction(self.push_first)[...]
