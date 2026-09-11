"""Implementation of the abstract syntax tree"""

import math
import operator
from dataclasses import dataclass
from types import EllipsisType
from typing import Any, Callable, Sequence, TypeAlias

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

ArgBounds: TypeAlias = tuple[int | EllipsisType, int | EllipsisType]


@dataclass(frozen=True, kw_only=True)
class Function:
    """A registry entry for a function"""

    names: Sequence[str]
    """Names of the function can be invoked with"""
    description: str
    """A short description of the function"""
    arg_bounds: ArgBounds
    """The minium and maximum number of parameters"""
    node_type: type[FunctionCallASTNode]
    """The type of resulting node"""

    @property
    def additional_kwargs(self) -> dict[str, Any]:
        """The keyword arguments needed for node init"""
        return {}


@dataclass(frozen=True, kw_only=True)
class ProxyFunction(Function):
    """Base class for a registry entries for proxy ProxyFunctionASTNodes"""

    function: Callable[..., Any]
    """The proxy function utilized by the ASTNode"""

    @property
    def additional_kwargs(self) -> dict[str, Any]:
        """The keyword arguments needed for node init"""
        return {"function": self.function}


@dataclass(frozen=True, kw_only=True)
class NumericFunction(ProxyFunction):
    """A registry entry for a numeric proxy function."""

    node_type: type[FunctionCallASTNode] = NumericFunctionCallASTNode


_EPSILON = 1e-12

FUNCTION_REGISTRY: Sequence[Function] = (
    NumericFunction(
        names=["sin"],
        description="The sinus function.",
        function=math.sin,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["cos"],
        description="The cosine function.",
        function=math.cos,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["tan"],
        description="The tangent function.",
        function=math.tan,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["exp"],
        description="The exponential function.",
        function=math.exp,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["abs"],
        description="Gets the absolute value for of the given input.",
        function=abs,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["floor", "trunc"],
        description="Get the greatest integers less or equal to the input.",
        function=int,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["round"],
        description=(
            "Returns the first argument rounded to the next integer if no"
            " second parameter is given. If a second parameter is given this"
            " specifies the length of resulting fractional part."
        ),
        function=round,
        arg_bounds=(1, 2),
    ),
    NumericFunction(
        names=["sgn", "sign"],
        description="Returns the sign of the given number (with a tolerance of +/- 1e-12).",
        function=lambda a: -1 if a < -_EPSILON else 1 if a > _EPSILON else 0,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["multiply"],
        description="Multiply two given values (legacy).",
        function=operator.mul,
        arg_bounds=(2, 2),
    ),
    NumericFunction(
        names=["hypot"],
        description="Multidimensional Euclidean distance from the origin to a point.",
        function=math.hypot,
        arg_bounds=(1, ...),
    ),
    NumericFunction(
        names=["min"],
        description="Get the minium of the passed values.",
        function=min,
        arg_bounds=(2, ...),
    ),
    NumericFunction(
        names=["max"],
        description="Get the maximum of the passed values.",
        function=max,
        arg_bounds=(2, ...),
    ),
    Function(
        names=["not"],
        description=(
            "Invert the passed boolean value. Returns False if input is True or"
            " non-null, True otherwise."
        ),
        arg_bounds=(1, 1),
        node_type=NotFunctionASTNode,
    ),
    Function(
        names=["all", "and"],
        description="Returns True all passed values are True or non-zero.",
        arg_bounds=(2, ...),
        node_type=AllFunctionASTNode,
    ),
    Function(
        names=["any", "or"],
        description="Returns True if one of the passed values is True or non-zero.",
        arg_bounds=(2, ...),
        node_type=AnyFunctionASTNode,
    ),
)
"""Registry for all functions available in the calculation expressions"""


_FUNCTION_NAME_MAP: dict[str, Function] = {
    name.lower(): info for info in FUNCTION_REGISTRY for name in info.names
}


def try_create_function_node(function_name: str, *children: ASTNode) -> FunctionCallASTNode:
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
    if not (function_info := _FUNCTION_NAME_MAP.get(function_name.lower())):
        raise UnknownFunctionError(f"Unknown function {function_name !r}.")
    min_param_count, max_param_count = function_info.arg_bounds
    if min_param_count is not Ellipsis and len(children) < min_param_count:
        raise InvalidSyntaxError(
            f"Function {function_name !r} required at least"
            f" {min_param_count} parameters got {len(children)}"
        )
    if max_param_count is not Ellipsis and len(children) > max_param_count:
        raise InvalidSyntaxError(
            f"Function {function_name !r} allows at maximum"
            f" {max_param_count} parameters got {len(children)}"
        )

    return function_info.node_type(
        function_name,
        *children,
        **function_info.additional_kwargs,
    )
