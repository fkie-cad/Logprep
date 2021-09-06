from typing import Optional, List

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.filter.expression.filter_expression import KeyDoesNotExistError


class Node:
    def __init__(self, expression: FilterExpression):
        self._expression = expression
        self._children = []
        self.matching_rules = []

    def does_match(self, event: dict):
        try:
            return self._expression.does_match(event)
        except KeyDoesNotExistError:
            return False

    def add_child(self, node: 'Node'):
        self._children.append(node)

    def has_child_with_expression(self, expression: FilterExpression) -> Optional['Node']:
        return self.get_child_with_expression(expression)

    def get_child_with_expression(self, expression: FilterExpression) -> Optional['Node']:
        for child in self._children:
            if child.expression == expression:
                return child

        return None

    @property
    def expression(self) -> FilterExpression:
        return self._expression

    @property
    def children(self) -> List['Node']:
        return self._children
