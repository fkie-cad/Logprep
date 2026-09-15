"""Implementation of the abstract syntax tree"""

import math
import operator
from typing import Any, Callable, Sequence

import attr

from logprep.processor.calculator.ast.exceptions import (
    InvalidSyntaxError,
    UnknownFunctionError,
)
from logprep.processor.calculator.ast.node import (
    AllFunctionASTNode,
    AnyFunctionASTNode,
    ASTNode,
    FunctionCallASTNode,
    NotFunctionASTNode,
    NumericFunctionCallASTNode,
)


@attr.define(frozen=True, kw_only=True)
class Function:
    """A registry entry for a function"""

    names: Sequence[str]
    """Names of the function can be invoked with"""

    description: str
    """A short description of the function"""

    min_args: int | None = None
    """The minium number of parameters"""

    max_args: int | None = None
    """The maximum number of parameters"""

    node_type: type[FunctionCallASTNode]
    """The type of resulting node"""

    def _check_param_count(self, function_name: str, count: int) -> None:
        """check the given number of params

        Parameters
        ----------
        function_name : str
            The function name to be displayed in the raised event.
        count : int
            The number of parameters given.

        Raises
        ------
        InvalidSyntaxError
            Raised if the number of parameters does not fit the specified
            `min_args` and `max_args` values.
        """
        if self.min_args is not None and count < self.min_args:
            raise InvalidSyntaxError(
                f"Function {function_name!r} required at least"
                f" {self.min_args} parameters got {count}"
            )
        if self.max_args is not None and count > self.max_args:
            raise InvalidSyntaxError(
                f"Function {function_name!r} allows at maximum"
                f" {self.max_args} parameters got {count}"
            )

    def create_node(self, function_name: str, *children: ASTNode) -> ASTNode:
        """Create an ASTNode instance implementing a function call
        towards the given function.

        Parameters
        ----------
        function_name : str
            The alias this function was invoked under.
        *children: ASTNode
            The ASTNode instances serving as arguments of the function call.

        Returns
        -------
        ASTNode
            An ASTNode implementing the requested function call.
        """
        self._check_param_count(function_name, len(children))
        return self.node_type(function_name, *children)


@attr.define(frozen=True, kw_only=True)
class ProxyFunction(Function):
    """Base class for a registry entries for proxy ProxyFunctionASTNodes"""

    function: Callable[..., Any]
    """The proxy function utilized by the ASTNode"""


@attr.define(frozen=True, kw_only=True)
class NumericFunction(ProxyFunction):
    """A registry entry for a numeric proxy function."""

    node_type: type[NumericFunctionCallASTNode] = NumericFunctionCallASTNode

    def create_node(self, function_name: str, *children: ASTNode) -> ASTNode:
        self._check_param_count(function_name, len(children))
        return self.node_type(
            function_name,
            self.function,
            *children,
        )


_EPSILON = 1e-12

FUNCTION_REGISTRY: Sequence[Function] = (
    NumericFunction(
        names=["sin"],
        description="The sinus function.",
        function=math.sin,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["cos"],
        description="The cosine function.",
        function=math.cos,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["tan"],
        description="The tangent function.",
        function=math.tan,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["exp"],
        description="The exponential function.",
        function=math.exp,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["abs"],
        description="Gets the absolute value for of the given input.",
        function=abs,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["floor", "trunc"],
        description="Get the greatest integers less or equal to the input.",
        function=int,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["round"],
        description=(
            "Returns the first argument rounded to the next integer if no"
            " second parameter is given. If a second parameter is given this"
            " specifies the length of resulting fractional part."
        ),
        function=round,
        min_args=1,
        max_args=2,
    ),
    NumericFunction(
        names=["sgn", "sign"],
        description="Returns the sign of the given number (with a tolerance of +/- 1e-12).",
        function=lambda a: -1 if a < -_EPSILON else 1 if a > _EPSILON else 0,
        min_args=1,
        max_args=1,
    ),
    NumericFunction(
        names=["multiply"],
        description="Multiply two given values (legacy).",
        function=operator.mul,
        min_args=2,
        max_args=2,
    ),
    NumericFunction(
        names=["hypot"],
        description="Multidimensional Euclidean distance from the origin to a point.",
        function=math.hypot,
        min_args=1,
    ),
    NumericFunction(
        names=["min"],
        description="Get the minium of the passed values.",
        function=min,
        min_args=2,
    ),
    NumericFunction(
        names=["max"],
        description="Get the maximum of the passed values.",
        function=max,
        min_args=2,
    ),
    Function(
        names=["not"],
        description=(
            "Invert the passed boolean value. Returns False if input is True or"
            " non-null, True otherwise."
        ),
        min_args=1,
        max_args=1,
        node_type=NotFunctionASTNode,
    ),
    Function(
        names=["all", "and"],
        description="Returns True all passed values are True or non-zero.",
        min_args=2,
        node_type=AllFunctionASTNode,
    ),
    Function(
        names=["any", "or"],
        description="Returns True if one of the passed values is True or non-zero.",
        min_args=2,
        node_type=AnyFunctionASTNode,
    ),
)
"""Registry for all functions available in the calculation expressions"""


_FUNCTION_NAME_MAP: dict[str, Function] = {
    name.lower(): info for info in FUNCTION_REGISTRY for name in info.names
}


def try_create_function_node(function_name: str, *children: ASTNode) -> ASTNode:
    """Factory method for Function calls.


    Parameters
    ----------
    function_name : str
        The name of the function that should be called.
    children : Sequence[ASTNode]
        The syntax tree nodes that represent the parameters for the call.

    Returns
    -------
    FunctionCallASTNode
        A syntax tree node representing a function call.

    Raises
    ------
    UnknownFunctionError
        Raised if the requested function is unknown.
    InvalidSyntaxError
        Raised if the number of passed children does not match the number of
        expected parameters.
    """

    function_info = _FUNCTION_NAME_MAP.get(function_name.lower())
    if not function_info:
        raise UnknownFunctionError(f"Unknown function {function_name!r}.")

    return function_info.create_node(
        function_name,
        *children,
    )
