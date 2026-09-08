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
        function=math.sin,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["cos"],
        function=math.cos,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["tan"],
        function=math.tan,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["exp"],
        function=math.exp,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["abs"],
        function=abs,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["trunc"],
        function=int,
        arg_bounds=(1, 1),
    ),
    NumericFunction(
        names=["round"],
        function=round,
        arg_bounds=(1, 2),
    ),
    NumericFunction(
        names=["sgn", "sign"],
        function=lambda a: -1 if a < -_EPSILON else 1 if a > _EPSILON else 0,
        arg_bounds=(1, 2),
    ),
    NumericFunction(names=["multiply"], function=operator.mul, arg_bounds=(2, 2)),
    NumericFunction(
        names=["hypot"],
        function=math.hypot,
        arg_bounds=(1, ...),
    ),
    NumericFunction(
        names=["min"],
        function=min,
        arg_bounds=(2, ...),
    ),
    NumericFunction(
        names=["max"],
        function=max,
        arg_bounds=(2, ...),
    ),
    Function(
        names=["not"],
        arg_bounds=(1, 1),
        node_type=NotFunctionASTNode,
    ),
    Function(
        names=["all", "and"],
        arg_bounds=(2, ...),
        node_type=AllFunctionASTNode,
    ),
    Function(
        names=["any", "or"],
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
