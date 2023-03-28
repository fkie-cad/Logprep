"""This module implements the tree node functionality for the tree model."""

from typing import Optional
from attrs import define, field

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.util.helper import KeyDoesNotExistError
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

    def has_child_with_expression(self, expression: FilterExpression) -> Optional["Node"]:
        """Check if node has child with given expression.

        This function checks if a node has a child with the given filter expression.
        It is used to iterate through a tree in the process of adding a new rule to a tree.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to check for.

        Returns
        -------
        has_child: bool
            Decision if the node has a child with the given expression.

        """
        return self.get_child_with_expression(expression)

    def get_child_with_expression(self, expression: FilterExpression) -> Optional["Node"]:
        """Get child of node with given expression.

        This function returns a node's child with the given expression or None if such child node
        does not exist.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to check for.

        Returns
        -------
        child: Node
            Child node with given expression, if such node exists.

        """
        for child in self.children:
            if child.expression == expression:
                return child

        return None
