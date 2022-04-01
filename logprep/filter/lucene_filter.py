"""This module contains functionality that allows interpreting lucene queries."""

from typing import List, Union, Optional
import re
from itertools import chain, zip_longest

import luqum
from luqum.parser import parser, ParseSyntaxError, IllegalCharacterError
from luqum.tree import OrOperation, AndOperation, Group, FieldGroup, SearchField, Phrase, Word, Not

from logprep.filter.expression.filter_expression import (
    Or,
    And,
    StringFilterExpression,
    WildcardStringFilterExpression,
    SigmaFilterExpression,
    RegExFilterExpression,
    Not as NotExpression,
    Exists,
    Null,
    Always,
    FilterExpression,
)


class LuceneFilterError(BaseException):
    """Base class for LuceneFilter related exceptions."""


class LuceneFilter:
    """A filter that allows using lucene query strings."""

    @staticmethod
    def create(query_string: str, special_fields: dict = None) -> FilterExpression:
        """Create a FilterExpression from a lucene query string.

        Parameters
        ----------
        query_string : str
           A lucene query string.
        special_fields : list, optional
           Determines if query_string should be processed as regex-query or sigma-query.

        Returns
        -------
        filter : FilterExpression
            A lucene query parsed into a FilterExpression.

        Raises
        ------
        LuceneFilterError
            Raises if lucene filter could not be built.

        """
        query_string = LuceneFilter._add_lucene_escaping(query_string)

        try:
            tree = parser.parse(query_string)
            transformer = LuceneTransformer(tree, special_fields)
        except (ParseSyntaxError, IllegalCharacterError) as error:
            raise LuceneFilterError(error)

        return transformer.build_filter()

    @staticmethod
    def _add_lucene_escaping(query_string):
        """Ignore all escaping and escape only double quotes so that lucene can be parsed."""
        matches = re.findall(r'.*?((?:\\)+").*?', query_string)
        for idx, match in enumerate(matches):
            length = len(match) - 1
            if length > 1:
                matches[idx] = matches[idx][:-1] + matches[idx]
                matches[idx] = "\\" + matches[idx]
        split = re.split(r'(?:\\)+"', query_string)
        query_string = "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

        query_string = re.sub(r'((?:\\)+"[\s\)]*(?:AND|OR|NOT|$))', r"\\\g<1>", query_string)
        return query_string


class LuceneTransformer:
    """A transformer that converts a luqum tree into a FilterExpression."""

    _special_fields_map = {
        "regex_fields": RegExFilterExpression,
        "wildcard_fields": WildcardStringFilterExpression,
        "sigma_fields": SigmaFilterExpression,
    }

    def __init__(self, tree: luqum.tree, special_fields: dict = None):
        self._tree = tree

        self._special_fields = dict()

        special_fields = special_fields if special_fields else dict()
        for key in self._special_fields_map.keys():
            self._special_fields[key] = (
                special_fields.get(key) if special_fields.get(key) else list()
            )

        self._last_search_field = None

    def build_filter(self) -> FilterExpression:
        """Transform luqum tree into FilterExpression

        Returns
        -------
        filter : FilterExpression
            A luqum.tree parsed into a FilterExpression.

        """
        return self._parse_tree(self._tree)

    def _parse_tree(self, tree: luqum.tree) -> FilterExpression:
        if isinstance(tree, OrOperation):
            return Or(*self._collect_children(tree))
        if isinstance(tree, AndOperation):
            return And(*self._collect_children(tree))
        if isinstance(tree, Not):
            return NotExpression(
                *self._collect_children(tree)
            )  # pylint: disable=no-value-for-parameter
        if isinstance(tree, Group):
            return self._parse_tree(tree.children[0])
        if isinstance(tree, SearchField):
            if isinstance(tree.expr, FieldGroup):
                self._last_search_field = tree.name
                parsed = self._parse_tree(tree.expr.children[0])
                self._last_search_field = None
                return parsed
            else:
                return self._create_field(tree)
        if isinstance(tree, Word):
            if self._last_search_field:
                return self._create_field_group_expression(tree)
            else:
                return self._create_value_expression(tree)
        if isinstance(tree, Phrase):
            if self._last_search_field:
                return self._create_field_group_expression(tree)
            else:
                return self._create_value_expression(tree)
        raise LuceneFilterError('The expression "{}" is invalid!'.format(str(tree)))

    def _create_field_group_expression(self, tree: luqum.tree) -> FilterExpression:
        """Creates filter expression that is resulting from a field group.

        Parameters
        ----------
        tree : luqum.tree
            luqum.tree to create field group expression from.

        Returns
        -------
        FilterExpression
            Parsed filter expression.

        """
        key = self._last_search_field.split(".")
        value = self._strip_quote_from_string(tree.value)
        value = self._remove_lucene_escaping(value)
        return self._get_filter_expression(key, value)

    def _collect_children(self, tree: luqum.tree) -> List[FilterExpression]:
        expressions = []
        for child in tree.children:
            expressions.append(self._parse_tree(child))
        return expressions

    def _create_field(self, tree: luqum.tree) -> Optional[FilterExpression]:
        if isinstance(tree.expr, (Phrase, Word)):
            key = tree.name.replace("\\", "")
            key = key.split(".")
            if tree.expr.value == "null":
                return Null(key)

            value = self._strip_quote_from_string(tree.expr.value)
            value = self._remove_lucene_escaping(value)
            return self._get_filter_expression(key, value)
        return None

    def _get_filter_expression(
        self, key: List[str], value
    ) -> Union[RegExFilterExpression, StringFilterExpression]:
        key_and_modifier = key[-1].split("|")
        if len(key_and_modifier) == 2:
            if key_and_modifier[-1] == "re":
                return RegExFilterExpression(key[:-1] + key_and_modifier[:-1], value)

        dotted_field = ".".join(key)
        if self._special_fields.items():
            for sf_key, sf_value in self._special_fields.items():
                if sf_value is True or dotted_field in sf_value:
                    return self._special_fields_map[sf_key](key, value)
        return StringFilterExpression(key, value)

    @staticmethod
    def _create_value_expression(word: luqum.tree) -> Union[Exists, Always]:
        value = word.value.replace("\\", "")
        value = value.split(".")
        if value == ["*"]:
            return Always(True)
        else:
            return Exists(value)

    @staticmethod
    def _strip_quote_from_string(string: str) -> str:
        if (string[0] == string[-1]) and (string[0] in ["'", '"']):
            return string[1:-1]
        return string

    @staticmethod
    def _remove_lucene_escaping(string):
        """Remove previously added lucene escaping so that double quotes will be
        interpreted correctly by wildcard parser."""
        matches = re.findall(r'.*?((?:\\)*").*?', string)
        for idx, match in enumerate(matches):
            length = len(match) - 1
            matches[idx] = "\\" * (length // 2 - 1) + '"'

        split = re.split(r'(?:\\)*"', string)
        string = "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

        backslashes = 0
        for x in range(len(string)):
            chara = string[len(string) - 1 - x]
            if chara == "\\":
                backslashes += 1
            else:
                break

        if backslashes > 0:
            string = string[:-backslashes] + "\\" * (backslashes // 2 - 2)

        return string
