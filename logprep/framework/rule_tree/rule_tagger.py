""" This module implements functionality to add tags to filter expressions. """

from typing import Union, List

from logprep.filter.expression.filter_expression import (
    StringFilterExpression,
    Exists,
    Not,
    KeyBasedFilterExpression,
)
from logprep.util.helper import get_dotted_field_list


class RuleTagger:
    """Adds tags to filter expressions."""

    __slots__ = ["_tag_map"]

    _tag_map: dict

    def __init__(self, tag_map: dict):
        """Used to add tags to rule filters.

        The idea behind tags is to improve a rule's processing time by checking the
        tag before processing the actual rule.

        Parameters
        ----------
        tag_map: dict
            Dictionary containing field names as keys and tags as values that is used to add special
            tags to the rule.

        """
        self._tag_map = tag_map

    def add(self, list_of_rule_expressions: List[List[Union[Exists, StringFilterExpression]]]):
        """Add tags to rule filter.

        This function adds tags to the parsed rule filter. Tags are added according to a defined
        tag_map dictionary where the keys are field names and the values are filter expressions.

        If a field name defined in tag_map.keys() is found in a rule segment's filter expressions,
        the corresponding filter expression tag is created and added to the rule's segments as
        first segment.

        Parameters
        ----------
        list_of_rule_expressions: list
            List containing parsed rules in a format where each rule consists of a list of filter
            expressions.

        """

        if not self._tag_map:
            return

        for rule_expressions in list_of_rule_expressions:
            self._add_tags_to_rule_expressions(rule_expressions)

    def _add_tags_to_rule_expressions(self, rule_expressions):
        """Iterate through all expressions and handle different cases"""
        for expression in rule_expressions.copy():
            next_expression = expression.children[0] if isinstance(expression, Not) else expression
            if self._expression_in_tag_map(next_expression):
                if Exists([self._tag_map[next_expression.key[0]]]) not in rule_expressions:
                    self._add_tag(rule_expressions, self._tag_map[next_expression.key[0]])

    def _expression_in_tag_map(self, expression):
        return (
            isinstance(expression, KeyBasedFilterExpression)
            and expression.key[0] in self._tag_map.keys()
        )

    @staticmethod
    def _add_tag(expressions: List[KeyBasedFilterExpression], tag_map_value: str):
        """Add tag helper function.

        This function implements the functionality to add a tag for _add_special_tags().

        If the tag to add already exists, the function skips the new tag.
        Furthermore, it is distinguished between tags that create a simple Exists-filter expression
        and StringFilter-expressions (containing a ":").

        Parameters
        ----------
        expressions: list
            List containing filter expressions representing the parsed rule.
        tag_map_value: str
            Value that is used to create the tag. If it contains a ":", a StringFilterExpression
            will be created.
            Else, an Exists-expression will be created.

        """
        if RuleTagger._tag_exists(expressions[0], tag_map_value):
            return

        if ":" in tag_map_value:
            key, value = tag_map_value.split(":")
            expressions.insert(0, StringFilterExpression(get_dotted_field_list(key), value))
        else:
            expressions.insert(0, Exists(tag_map_value.split(".")))

    @staticmethod
    def _tag_exists(expression: KeyBasedFilterExpression, tag: str) -> bool:
        """Check if the given segment is equal to the given tag.

        Parameters
        ----------
        expression: Union[Exists, StringFilterExpression]
            Expression to check if equal to tag.
        tag: str
            Tag to check for.

        Returns
        -------
        tag_exists: bool
            Decision if the given tag already exists as the given segment.

        """
        if isinstance(expression, Exists):
            if repr(expression).rstrip(": *") == tag:
                return True
        elif isinstance(expression, StringFilterExpression):
            if repr(expression).replace('"', "") == tag:
                return True
        return False
