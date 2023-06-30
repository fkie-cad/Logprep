"""Module implements functionality to apply De Morgan's law on rule filter expressions"""
from logprep.filter.expression.filter_expression import (
    Not,
    And,
    Or,
    FilterExpression,
    CompoundFilterExpression,
)


class DeMorganResolverException(Exception):
    """Raise if demorgan resolver encounters a problem."""


class DeMorganResolver:
    """Used to apply De Morgan's law on rule filter expressions"""

    def resolve(self, expression: FilterExpression) -> FilterExpression:
        """Parse NOT-expressions in given filter expression.

        This function resolves NOT-expressions found in the given filter expression according to
        De Morgan's law.

        Parameters
        ----------
        expression: FilterExpression
            Given filter expression to be parsed.

        Returns
        -------
        result: FilterExpression
            Resulting filter expression created by resolving NOT-expressions in the given filter
            expression.

        """
        if not self._has_unresolved_expression(expression):
            return expression

        if isinstance(expression, Not):
            return self._resolve_not_expression(expression)
        if isinstance(expression, CompoundFilterExpression):
            return self._resolve_compound_expression(expression)

        raise DeMorganResolverException(f"Could not resolve expression {expression}")

    @staticmethod
    def _has_unresolved_expression(expression: FilterExpression) -> bool:
        """Check if given filter expression contains NOT-expressions.

        This function checks if the given filter expression contains any unresolved NOT-expressions.
        Simple NOT(field: value) expressions do not count as unresolved expression since it cannot
        be resolved.

        This is achieved by iterating over the input expression and all of its sub expressions.
        The input expression needs to be resolved if a negated compound expression is found.
        Otherwise, no resolving is required.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to be checked for NOT-expressions.

        Returns
        -------
        has_unresolved_not_expression: bool
            Decision if given filter expression contains any unresolved NOT-expressions.

        """
        expressions_stack = [expression]
        while expressions_stack:
            current_expression = expressions_stack.pop()
            if isinstance(current_expression, Not):
                if isinstance(current_expression.child, CompoundFilterExpression):
                    return True
            if isinstance(current_expression, CompoundFilterExpression):
                for sub_expression in current_expression.children:
                    expressions_stack.append(sub_expression)
        return False

    def _resolve_not_expression(self, not_expression: Not) -> FilterExpression:
        if not isinstance(not_expression.child, CompoundFilterExpression):
            return not_expression

        compound_expression = not_expression.child
        negated_children = (Not(expression) for expression in compound_expression.children)

        if isinstance(compound_expression, Or):
            expression = And(*negated_children)
        elif isinstance(compound_expression, And):
            expression = Or(*negated_children)
        else:
            raise DeMorganResolverException(f"Could not resolve expression {not_expression}")

        return self._resolve_compound_expression(expression)

    def _resolve_compound_expression(
        self, compound_expression: CompoundFilterExpression
    ) -> CompoundFilterExpression:
        compound_expression.children = tuple(
            self.resolve(expression) for expression in compound_expression.children
        )
        return compound_expression
