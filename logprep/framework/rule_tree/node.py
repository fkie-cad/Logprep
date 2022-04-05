"""This module implements the tree node functionality for the tree model."""

from typing import Optional, List

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.filter.expression.filter_expression import KeyDoesNotExistError


class Node:
    """Tree node for rule tree model."""

    def __init__(self, expression: FilterExpression):
        """Node initialization function.

        Initializes a new node with a given expression and empty lists of children and matching
        rules.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to be used by the new node.

        """
        self._expression = expression
        self._children = []
        self.matching_rules = []

    def does_match(self, event: dict):
        """Check if node matches given event.

        This function checks if the node's filter expression matches a given event dict.

        If the filter expression's key to be checked does not exist in the given event,
        the KeyDoesNotExistError is caught and False is returned.

        Parameters
        ----------
        event: dict
            Event dictionary to be checked.

        Returns
        -------
        matches: bool
            Decision if the given event matches the node's filter expression.

        """
        try:
            return self._expression.does_match(event)
        except KeyDoesNotExistError:
            return False

    def add_child(self, node: "Node"):
        """Add child to node.

        This function adds a given child node to the node by appending it to the list of the node's
        children.

        Parameters
        ----------
        node: Node
            Child node to add to the node.

        """
        self._children.append(node)

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
        for child in self._children:
            if child.expression == expression:
                return child

        return None

    @property
    def expression(self) -> FilterExpression:
        return self._expression

    @property
    def children(self) -> List["Node"]:
        return self._children
