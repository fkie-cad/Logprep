import math
import operator
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Protocol, Sequence, TypeAlias

from logprep.processor.calculator.ast.exceptions import (
    DivisionByZeroError,
    EvaluationError,
    InvalidSyntaxError,
    MissingValueError,
    UnknownFunctionError,
)
from logprep.processor.calculator.ast.util import (
    ValueType,
    parse_value,
    read_hex_number,
)
from logprep.util.helper import MISSING, FieldValue, get_dotted_field_value_with_missing


class ASTWalkContext(Protocol):
    def visit(self, node: "ASTNode", *children: "ASTNode") -> None: ...


NodeId: TypeAlias = int
NodeDesc: TypeAlias = str


class DiagramRenderContext(ASTWalkContext):
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
    diagram_render_context = DiagramRenderContext()
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


_VALUE_CLASS: dict[ValueType, type[ConstantASTNode]] = {
    ValueType.NUMBER: ConstantNumberASTNode,
    ValueType.BOOLEAN: ConstantBooleanASTNode,
}


class VariableASTNode(TerminalASTNode):
    output_type = ValueType.NUMBER

    def __init__(self, path: str):
        self.path = path

    @property
    def is_constant(self):
        return False

    def _get_context_value(self, context: EvaluationContext) -> Any:
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
    def _get_context_value(self, context):
        raw_value = super()._get_context_value(context)
        return read_hex_number(raw_value)


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
            return ConstantNumberASTNode(-_constant_value(optimized_inner))
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
                    _constant_value(lhs_optimized),
                    _constant_value(rhs_optimized),
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
        return f"<op {self.operator_symbol !r}>"


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
        try:
            return super().evaluate(context)
        except ZeroDivisionError as error:
            # division and power operator might run into ZeroDevisionErrors
            # we want to repack those into a class inheriting from LogprepException
            raise DivisionByZeroError("Division by zero.") from error


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


class ModASTNode(ArithmeticASTNode):
    operator_symbol = "%"
    operation_fn = operator.mod

    def _operation_specific_optimizations(self, lhs, rhs):
        if _is_constant_value(rhs, 0):
            raise DivisionByZeroError("Expression resulted to a division by zero on optimization.")
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
        return ConstantBooleanASTNode(_constant_value(self))


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
            return ConstantBooleanASTNode(_constant_value(self))
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

    supported_functions: ClassVar[dict[str, Callable[..., Any]]]

    @classmethod
    def implements(cls, function_name: str) -> bool:
        return function_name in cls.supported_functions

    def __init__(self, function_name: str, children: Sequence[ASTNode]):
        super().__init__(*children)
        if function_name not in self.supported_functions:
            raise UnknownFunctionError(f"Unknown function {function_name !r}")
        self.function_name = function_name

    def optimize(self) -> ASTNode:
        optimized_clone = type(self)(
            function_name=self.function_name,
            children=[child.optimize() for child in self.children],
        )
        if not all(child.is_constant for child in optimized_clone.children):
            return optimized_clone

        my_static_value = _constant_value(optimized_clone)
        return _VALUE_CLASS[self.input_type](value=my_static_value)

    def evaluate(self, context):
        operands = [child.evaluate(context) for child in self.children]
        try:
            return self.supported_functions[self.function_name](*operands)
        except Exception as error:
            raise EvaluationError(
                f"Failed on operator {self.function_name !r} with values {operands !r}"
            ) from error

    def __repr__(self):
        return f"<func {self.function_name !r}>"


# TODO check f we want to keep this
_EPSILON = 1e-12


class NumericFunctionCallASTNode(FunctionCallASTNode):
    supported_functions = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "exp": math.exp,
        "abs": abs,
        "trunc": int,
        "from_hex": lambda a: int(a, 16),
        "round": round,
        "sgn": lambda a: -1 if a < -_EPSILON else 1 if a > _EPSILON else 0,
        # functions with multiple arguments
        "multiply": lambda a, b: a * b,
        "hypot": math.hypot,
    }
    input_type = ValueType.NUMBER
    output_type = ValueType.NUMBER


class AllFunctionASTNode(CompositeASTNode):
    input_type = ValueType.BOOLEAN
    output_type = ValueType.BOOLEAN

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
        if len(optimized_children) == 1:
            return optimized_children[0]
        optimized_children.sort(key=lambda child: child.complexity)
        return type(self)(*optimized_children)

    def __repr__(self):
        return "<all>"


class AnyFunctionASTNode(CompositeASTNode):
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
        if len(optimized_children) == 1:
            return optimized_children[0]
        optimized_children.sort(key=lambda child: child.complexity)
        return type(self)(*optimized_children)

    def __repr__(self):
        return "<any>"
