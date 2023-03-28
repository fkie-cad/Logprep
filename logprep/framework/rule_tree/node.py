"""This module implements the tree node functionality for the tree model."""

from attrs import define, field

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule


@define(slots=True)
class Node:
    """Tree node for rule tree model."""

    expression: FilterExpression

    children: dict["Node", None] = field(factory=dict, eq=False, repr=False)

    matching_rules: dict[Rule] = field(factory=dict, eq=False, repr=False)

    def __hash__(self) -> int:
        return id(self.expression)

    def __eq__(self, node: "Node") -> bool:
        return self is node

    def add_child(self, node: "Node"):
        """Add child to node.

        This function adds a given child node to the node by appending it to the list of the node's
        children.

        Parameters
        ----------
        node: Node
            Child node to add to the node.

        """
        self.children |= {node: None}

    @property
    def child_expressions(self):
        return {child.expression: None for child in self.children}
