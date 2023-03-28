"""This module implements the tree node functionality for the tree model."""

from attrs import define, field

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule


@define(slots=True)
class Node:
    """Tree node for rule tree model."""

    expression: FilterExpression = field()

    children: list["Node", None] = field(factory=list, eq=False, repr=False)

    matching_rules: list[Rule] = field(factory=list, eq=False, repr=False)

    child_expressions: set[FilterExpression] = field(factory=set, eq=False, repr=False)

    def __attrs_post_init__(self):
        if isinstance(self.expression, list):
            self.expression = self.expression[0]
            for expression in self.expression:
                self.add_child(Node(expression))

    def __hash__(self) -> int:
        return hash(repr(self))

    def add_child(self, node: "Node") -> bool:
        """Add child to node.

        This function adds a given child node to the node by appending it to the list of the node's
        children.

        Parameters
        ----------
        node: Node
            Child node to add to the node.

        """
        if self == node:
            self.matching_rules += node.matching_rules
            self.child_expressions |= node.child_expressions
            return True
        if not self.children:
            self.children.append(node)
            self.child_expressions |= {node.expression}
        for child in self.children:  # pylint: disable=not-an-iterable
            success = child.add_child(node)
            if success:
                self.child_expressions |= {node.expression}
                return True
        return False

    def add_rule(self, rule_filters: list, rule: Rule) -> None:
        for parsed_rule in rule_filters:
            end_node = self._add_parsed_rule(parsed_rule)
            if rule not in end_node.matching_rules:
                end_node.matching_rules += (rule,)
