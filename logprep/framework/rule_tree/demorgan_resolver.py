"""Module implements functionality to apply De Morgan's law on rule filter expressions"""

from logprep.abc.exceptions import LogprepException
from logprep.filter.expression.filter_expression import (
    And,
    CompoundFilterExpression,
    FilterExpression,
    Not,
    Or,
)


class DeMorganResolverException(LogprepException):
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
        if isinstance(expression, Not):
            return self._resolve_not_expression(expression)
        if isinstance(expression, CompoundFilterExpression):
            return self._resolve_compound_expression(expression)

        return expression

    def _resolve_not_expression(self, not_expression: Not) -> FilterExpression:
        if not isinstance(not_expression, Not):
            raise DeMorganResolverException(
                f'Can\'t resolve expression "{not_expression}", since it\'s not of the type "NOT."'
            )

        if not isinstance(not_expression.children[0], CompoundFilterExpression):
            return not_expression

        compound_expression = not_expression.children[0]
        negated_children = (Not(expression) for expression in compound_expression.children)

        if isinstance(compound_expression, Or):
            expression = And(*negated_children)
        elif isinstance(compound_expression, And):
            expression = Or(*negated_children)
        else:
            raise DeMorganResolverException(
                f'Could not resolve expression "{not_expression}", '
                f'since its child is neither of the type "AND" nor "OR".'
            )

        return self._resolve_compound_expression(expression)

    def _resolve_compound_expression(
        self, compound_expression: CompoundFilterExpression
    ) -> CompoundFilterExpression:
        compound_expression.children = tuple(
            self.resolve(expression) for expression in compound_expression.children
        )
        return compound_expression
