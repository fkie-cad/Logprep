"""This module implements functionality to sort rule filter segments."""

from typing import Union

from logprep.abc.exceptions import LogprepException
from logprep.filter.expression.filter_expression import (
    Always,
    FilterExpression,
    KeyBasedFilterExpression,
    Not,
)


class RuleSorterException(LogprepException):
    """Raise if rule sorter encounters a problem."""


class RuleSorter:
    """Sorts rule filter segments."""

    @staticmethod
    def sort_rule_segments(parsed_rule_list: list, priority_dict: dict):
        """Sort filter expressions in rule.

        This function sorts the filter expressions in all parsed rules without changing the rule's
        decision behavior.
        The expressions are sorted alphabetically or according to a defined priority dictionary.

        Goal of the sorting process is to achieve better processing times using the defined
        priorities and to minimize the resulting tree by ensuring an order in which fields to be
        checked occur in all rules.

        Parameters
        ----------
        parsed_rule_list: list
            List of parsed rules where every rule is a list of filter expressions.
        priority_dict: dict
            Dictionary with sorting priority information (key -> field name; value -> priority).

        """
        sorting_keys = {}
        for parsed_rule in parsed_rule_list:
            for parsed_expression in parsed_rule:
                expression_repr = repr(parsed_expression)
                if expression_repr not in sorting_keys:
                    sorting_keys[expression_repr] = RuleSorter._get_sorting_key(
                        parsed_expression, priority_dict
                    )
        for parsed_rule in parsed_rule_list:
            parsed_rule.sort(key=lambda expression: sorting_keys.get(repr(expression)))

    @staticmethod
    def _get_sorting_key(
        expression: FilterExpression, priority_dict: dict
    ) -> Union[dict, str, None]:
        """Get the sorting key for an expression with a priority dict.

        This function is used by the _sort_rule_segments() function in the sorting key.
        It includes various cases to cover all the different expression classes. For every class it
        tries to get a priority value from the priority dict. If the field name used in the
        expression does not exist in the priority dict, the field name itself is returned to use an
        alphabetical sort.

        Parameters
        ----------
        expression: FilterExpression
            Filter expression to get comparison value for.
        priority_dict: dict
            Dictionary with sorting priority information (key -> field name; value -> priority).

        Returns
        -------
        comparison_value: Union[dict, str, None]
            Comparison value to use for sorting.

        """
        if isinstance(expression, Always):
            return None

        if isinstance(expression, Not):
            return RuleSorter._sort_not_expression(expression, priority_dict)

        if isinstance(expression, KeyBasedFilterExpression):
            return priority_dict.get(expression.key_as_dotted_string, repr(expression))

        raise RuleSorterException(f'Could not sort "{expression}"')

    @staticmethod
    def _sort_not_expression(expression, priority_dict):
        try:
            if isinstance(expression.children[0], Not):
                if isinstance(expression.children[0].children[0], KeyBasedFilterExpression):
                    return priority_dict[expression.children[0].children[0].key[0]]

            if isinstance(expression.children[0], KeyBasedFilterExpression):
                return priority_dict[expression.children[0].key_as_dotted_string]
        except KeyError:
            pass
        return RuleSorter._get_sorting_key(expression.children[0], priority_dict)
