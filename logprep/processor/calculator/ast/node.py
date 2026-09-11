"""Implementation of the abstract syntax tree"""

import operator
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Protocol, TypeAlias

from logprep.processor.calculator.ast.exceptions import (
    DivisionByZeroError,
    InvalidSyntaxError,
    MissingValueError,
)
from logprep.processor.calculator.ast.util import (
    ValueType,
    parse_value,
    read_hex_number,
)
from logprep.util.helper import MISSING, FieldValue, get_dotted_field_value_with_missing


class ASTWalkContext(Protocol):
    """Protocol for scanning the abstract syntax tree by visitor pattern."""

    def visit(self, node: "ASTNode", *children: "ASTNode") -> None:
        """The callback for visiting a node.

        Parameters
        ----------
        node : ASTNode
            The visited node.
        children : ASTNode
            The children of the visited node.

        """


NodeId: TypeAlias = int
NodeDesc: TypeAlias = str


class _DiagramRenderContext(ASTWalkContext):
    """Utility for the get_ast_diagram function"""

    def __init__(self) -> None:
        self.__counter = 0
        self.__id_to_counter: dict[NodeId, int] = {}
        self.nodes: dict[NodeId, NodeDesc] = {}
        self.links: list[tuple[NodeId, NodeId]] = []

    def visit(self, node: "ASTNode", *children: "ASTNode"):
        if id(node) not in self.__id_to_counter:
            self.__id_to_counter[id(node)] = self.__counter
            self.__counter += 1
        self.nodes[id(node)] = repr(node)
        self.links.extend((id(node), id(child)) for child in children)

    def get_graph_viz(self) -> str:
        """Render the scanned syntax tree in GraphViz format.

        Returns
        -------
        str
            The code for a diagram in GraphViz.
        """

        def _node_ref(node_id: NodeId) -> str:
            return f"n{self.__id_to_counter[node_id]}"

        return "\n".join(
            ["digraph {"]
            + [
                f'    {_node_ref(node_id)} [label = "{node_desc}";];'
                for node_id, node_desc in self.nodes.items()
            ]
            + [
                f"    {_node_ref(parent_id)} -> {_node_ref(child_id)};"
                for parent_id, child_id in self.links
            ]
            + ["}"]
        )


def get_ast_diagram(node: "ASTNode") -> str:
    """Visualize a syntax tree as a GraphViz diagram.

    Parameters
    ----------
    node : ASTNode
        The root node of the abstract syntax tree to visualize.

    Returns
    -------
    str
        The GraphViz code of the diagram visualizing the AST.
    """
    diagram_render_context = _DiagramRenderContext()
    node.walk(diagram_render_context)
    return diagram_render_context.get_graph_viz()


EvaluationContext: TypeAlias = dict[str, FieldValue]

EMPTY_CONTEXT: EvaluationContext = {}


def _constant_value(node: "ASTNode"):
    assert node.is_constant
    return node.evaluate(EMPTY_CONTEXT)


def _is_constant_value(node: "ASTNode", value: int) -> bool:
    return node.is_constant and _constant_value(node) == value


class ASTNode(ABC):
    """Abstract base class for nodes in the abstract syntax tree"""

    output_type: ClassVar[ValueType]
    """Output type of the node."""

    @abstractmethod
    def walk(self, context: ASTWalkContext) -> None:
        """Function used to scan the syntax tree by visitor pattern.
        Will recursively call the walk function on child nodes.

        Parameters
        ----------
        context : ASTWalkContext
            The context object used for scanning the AST.
        """

    @abstractmethod
    def evaluate(self, context: EvaluationContext) -> Any:
        """Evaluate the Syntax Tree for the given context.

        Parameters
        ----------
        context : EvaluationContext
            The context used for the evaluation.

        Returns
        -------
        Any
            The result of the evaluation, the type must adhere to the nodes
            specified output_type.
        """

    @property
    @abstractmethod
    def is_constant(self) -> bool:
        """True if the evaluation does not depend on the passed context"""

    @property
    @abstractmethod
    def complexity(self) -> int:
        """A number indicating how complex the evaluation of a node is"""

    @abstractmethod
    def optimize(self) -> "ASTNode":
        """Get an optimized version of the node.

        Returns
        -------
        ASTNode
           An optimized version of this node. Will return a deepcopy if no
           optimization is possible for consistency.

        Raises
        ------
        DivisionByZeroError
            Some optimizations might result in detecting a zero division.

        """


class TerminalASTNode(ASTNode):
    """Base type for leafs in the syntax tree"""

    @property
    def complexity(self):
        return 1

    def walk(self, context):
        return context.visit(self)


class ConstantASTNode(TerminalASTNode):
    """Base type for nodes representing constant values"""

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
    """A node representing a constant number"""

    output_type = ValueType.NUMBER


class ConstantBooleanASTNode(ConstantASTNode):
    """A node representing a constant boolean"""

    output_type = ValueType.BOOLEAN


_VALUE_CLASS: dict[ValueType, type[ConstantASTNode]] = {
    ValueType.NUMBER: ConstantNumberASTNode,
    ValueType.BOOLEAN: ConstantBooleanASTNode,
}


class VariableASTNode(TerminalASTNode):
    """A node representing a variable to be read from the context"""

    output_type = ValueType.NUMBER

    def __init__(self, path: str):
        self.path = path

    @property
    def is_constant(self):
        return False

    def _get_context_value(self, context: EvaluationContext) -> Any:
        """Get the raw return value from the context passed during evaluation.

        Parameters
        ----------
        context : EvaluationContext
            The context used for evaluating the syntax tree.

        Returns
        -------
        Any
            The value read from the context at the nodes path.

        Raises
        ------
        MissingValueError
            Raised if the requested path is missing in the passed context.
        """
        value = get_dotted_field_value_with_missing(context, self.path)
        if value is MISSING:
            raise MissingValueError(f"Missing value for field {self.path!r}.")
        return value

    def evaluate(self, context):
        value = self._get_context_value(context)
        return parse_value(value, self.output_type)

    def __repr__(self):
        return f"<variable {self.path !r}>"

    def optimize(self):
        return type(self)(path=self.path)


class HexNumberVariableASTNode(VariableASTNode):
    """A node representing a number read from a hex-string in the context"""

    def _get_context_value(self, context):
        raw_value = super()._get_context_value(context)
        return read_hex_number(raw_value)


class CompositeASTNode(ASTNode):
    """Base class for non-terminal nodes (those representing the branches)"""

    input_type: ClassVar[ValueType]
    """The input type of the node.
    The output_types of the children need to be parsable to this"""

    def __init__(self, *children: ASTNode):
        if not all(child.output_type.can_be_cast_to(self.input_type) for child in children):
            raise InvalidSyntaxError(f"Can not parse all inputs to {self.input_type}.")

        self.children = children
        """The children enwrapped by this node"""

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
    """A node representing an unary minus"""

    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    def __init__(self, inner: ASTNode):
        super().__init__(inner)
        self.inner = inner

    def optimize(self):
        optimized_inner = self.inner.optimize()
        if optimized_inner.is_constant:
            return ConstantNumberASTNode(-_constant_value(optimized_inner))
        return NegateASTNode(optimized_inner)

    def evaluate(self, context):
        return -self.inner.evaluate(context)

    def __repr__(self) -> str:
        return "<negate>"


class OperationASTNode(CompositeASTNode):
    """Base node for nodes representing an operation with two operands"""

    operator_symbol: ClassVar[str]
    """The symbol representing the operation"""

    operation_fn: ClassVar[Callable[[Any, Any], Any]]
    """The callback internally used to evaluate the operation"""

    def __init__(
        self,
        lhs: ASTNode,
        rhs: ASTNode,
    ):
        super().__init__(lhs, rhs)
        self.lhs = lhs
        """The left-hand-side operand of the operation"""
        self.rhs = rhs
        """The right-hand-side operand of the operation"""

    def _operation_specific_optimizations(self, lhs: ASTNode, rhs: ASTNode) -> ASTNode | None:
        # pylint: disable=unused-argument
        """Override this to implement specific optimizations for the specific
        operation.

        Parameters
        ----------
        lhs : ASTNode
            The (already optimized) left-hand-side of the operation.
        rhs : ASTNode
            The (already optimized) right-hand-side of the operation.

        Returns
        -------
        ASTNode | None
            If ASTNode is returned this will be used as the optimized operation.
            If None is returned the optimized result will be constructed from
            the optimized lhs and rhs nodes.
        """
        return None

    def optimize(self):
        lhs_optimized = self.lhs.optimize()
        rhs_optimized = self.rhs.optimize()

        if lhs_optimized.is_constant and rhs_optimized.is_constant:
            try:
                return _VALUE_CLASS[self.output_type](
                    self.operation_fn(
                        _constant_value(lhs_optimized),
                        _constant_value(rhs_optimized),
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
        return self.operation_fn(
            self.lhs.evaluate(context),
            self.rhs.evaluate(context),
        )

    def __repr__(self) -> str:
        return f"<op {self.operator_symbol !r}>"


class ArithmeticASTNode(OperationASTNode):
    """Base node for arithmetic operations"""

    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER


class AddASTNode(ArithmeticASTNode):
    """Node representing an addition operation"""

    operator_symbol = "+"
    operation_fn = operator.add

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            return lhs
        if _is_constant_value(lhs, 0):
            return rhs
        return None


class SubASTNode(ArithmeticASTNode):
    """Node representing an subtraction operation"""

    operator_symbol = "-"
    operation_fn = operator.sub

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            return lhs
        if _is_constant_value(lhs, 0):
            return NegateASTNode(rhs).optimize()
        return None


class MulASTNode(ArithmeticASTNode):
    """Node representing a multiplication operation"""

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


class DivArithmeticASTNode(ArithmeticASTNode):
    """Base class for arithmetic operations that might result in a
    DivisionByZero exception"""

    def evaluate(self, context):
        try:
            return super().evaluate(context)
        except ZeroDivisionError as error:
            raise DivisionByZeroError("Division by zero.") from error


class DivASTNode(DivArithmeticASTNode):
    """Node representing a division operation"""

    operator_symbol = "/"
    operation_fn = operator.truediv

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            raise DivisionByZeroError("Expression resulted to a division by zero on optimization.")
        if _is_constant_value(rhs, 1):
            return lhs
        return None


class ModASTNode(DivArithmeticASTNode):
    """Node representing a modulo operation"""

    operator_symbol = "%"
    operation_fn = operator.mod

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            raise DivisionByZeroError("Expression resulted to a division by zero on optimization.")


class PowASTNode(DivArithmeticASTNode):
    """Node representing a power operation"""

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
    """Base for nodes representing an comparison operation"""

    input_type = ValueType.NUMBER
    output_type = ValueType.BOOLEAN


class EqualASTNode(ComparisonASTNode):
    """A node representing a equal comparison"""

    operator_symbol = "=="
    operation_fn = operator.eq


class UnequalASTNode(ComparisonASTNode):
    """A node representing a unequal comparison"""

    operator_symbol = "!="
    operation_fn = operator.ne


class LessThanASTNode(ComparisonASTNode):
    """A node representing a less then comparison"""

    operator_symbol = "<"
    operation_fn = operator.lt


class LessOrEqualThanASTNode(ComparisonASTNode):
    """A node representing a less or equal comparison"""

    operator_symbol = "<="
    operation_fn = operator.le


class GreaterThanASTNode(ComparisonASTNode):
    """A node representing a greater than comparison"""

    operator_symbol = ">"
    operation_fn = operator.gt


class GreaterOrEqualThanASTNode(ComparisonASTNode):
    """A node representing a greater or equal comparison"""

    operator_symbol = ">="
    operation_fn = operator.ge


class RangeCheckASTNode(CompositeASTNode):
    """A node representing a range check (i.e. a < b < c)"""

    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER

    def __init__(
        self,
        lower_bound: ASTNode,
        value: ASTNode,
        upper_bound: ASTNode,
        *,
        lower_bound_is_inclusive: bool = False,
        upper_bound_is_inclusive: bool = False,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(lower_bound, value, upper_bound)
        self.lower_bound = lower_bound
        self.lower_bound_is_inclusive = lower_bound_is_inclusive
        self.value = value
        self.upper_bound = upper_bound
        self.upper_bound_is_inclusive = upper_bound_is_inclusive

    def optimize(self):
        if self.is_constant:
            return ConstantBooleanASTNode(_constant_value(self))
        return type(self)(
            self.lower_bound.optimize(),
            self.value.optimize(),
            self.upper_bound.optimize(),
            lower_bound_is_inclusive=self.lower_bound_is_inclusive,
            upper_bound_is_inclusive=self.upper_bound_is_inclusive,
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
        ModASTNode,
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
    """A node representing a function call"""

    def __init__(
        self,
        function_name: str,
        *children: ASTNode,
    ):
        super().__init__(*children)
        self.function_name = function_name
        """The name of the function"""

    def __repr__(self):
        return f"<func {self.function_name !r}>"


class ProxyFunctionCallASTNode(FunctionCallASTNode):
    """Base class for FunctionCall nodes that utilize a callback function"""

    def __init__(
        self,
        function_name: str,
        *children: ASTNode,
        function: Callable[..., Any],
    ):
        super().__init__(function_name, *children)
        self.function = function
        """The actual function to call"""

    def evaluate(self, context):
        return self.function(*(child.evaluate(context) for child in self.children))

    def optimize(self) -> ASTNode:
        optimized_clone = type(self)(
            self.function_name,
            *(child.optimize() for child in self.children),
            function=self.function,
        )
        if not all(child.is_constant for child in optimized_clone.children):
            return optimized_clone

        my_static_value = _constant_value(optimized_clone)
        return _VALUE_CLASS[self.input_type](value=my_static_value)


class NumericFunctionCallASTNode(ProxyFunctionCallASTNode):
    """A node representing functions that take numbers and return a number"""

    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER


class LogicFunctionASTNode(FunctionCallASTNode):
    """Base type for functions operating on booleans"""

    input_type = ValueType.BOOLEAN
    output_type = ValueType.BOOLEAN


class NotFunctionASTNode(LogicFunctionASTNode):
    """A node representing the 'not' function."""

    def evaluate(self, context):
        return not parse_value(
            self.children[0].evaluate(context),
            self.input_type,
        )

    def optimize(self):
        optimized_inner = self.children[0].optimize()
        if optimized_inner.is_constant:
            return ConstantBooleanASTNode(
                not parse_value(
                    _constant_value(optimized_inner),
                    ValueType.BOOLEAN,
                )
            )
        return type(self)(self.function_name, optimized_inner)


class AllFunctionASTNode(LogicFunctionASTNode):
    """A node representing an 'all' function call."""

    def evaluate(self, context):
        for child in self.children:
            if not child.evaluate(context):
                return False
        return True

    def optimize(self):
        if all(child.is_constant for child in self.children):
            return ConstantBooleanASTNode(all(_constant_value(child) for child in self.children))
        if any(child.is_constant and not _constant_value(child) for child in self.children):
            return ConstantBooleanASTNode(False)
        optimized_children = [child.optimize() for child in self.children if not child.is_constant]
        optimized_children.sort(key=lambda child: child.complexity)
        return type(self)(self.function_name, *optimized_children)


class AnyFunctionASTNode(LogicFunctionASTNode):
    """A node representing an 'any' function call"""

    input_type = ValueType.BOOLEAN
    output_type = ValueType.BOOLEAN

    def evaluate(self, context):
        for child in self.children:
            if child.evaluate(context):
                return True
        return False

    def optimize(self):
        if all(child.is_constant for child in self.children):
            return ConstantBooleanASTNode(any(_constant_value(child) for child in self.children))
        if any(child.is_constant and _constant_value(child) for child in self.children):
            return ConstantBooleanASTNode(True)
        optimized_children = [child.optimize() for child in self.children if not child.is_constant]
        optimized_children.sort(key=lambda child: child.complexity)
        return type(self)(self.function_name, *optimized_children)
