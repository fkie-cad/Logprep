# pylint: disable=anomalous-backslash-in-string
r"""
Filter
======

The filters are based on the Lucene query language, but contain some additional enhancements.
It is possible to filter for keys and values in log messages.
**Dot notation** is used to access subfields in log messages.
A filter for :code:`{'field': {'subfield': 'value'}}` can be specified by
:code:`field.subfield': 'value'`.

If a key without a value is given it is filtered for the existence of the key.
The existence of a specific field can therefore be checked by a key without a value.
The filter :code:`filter: field.subfield` would match for every value :code:`subfield` in
:code:`{'field': {'subfield': 'value'}}`.
The special key :code:`*` can be used to always match on any input.
Thus, the filter :code:`filter: *` would match any input document.

The filter in the following example would match fields :code:`ip_address` with the
value :code:`192.168.0.1`.
Meaning all following transformations done by this rule would be applied only
on log messages that match this criterion.
This example is not complete, since rules are specific to processors and require additional options.


..  code-block:: json
    :linenos:
    :caption: Example

    { "filter": "ip_address: 192.168.0.1" }

It is possible to use filters with field names that contain white spaces or use special symbols
of the Lucene syntax. However, this has to be escaped.
The filter :code:`filter: 'field.a subfield(test): value'` must be escaped as
:code:`filter: 'field.a\\\ subfield\(test\): value'`.
Other references to this field do not require such escaping.
This is *only* necessary for the filter.
It is necessary to escape twice if the file is in the JSON format - once for
the filter itself and once for JSON.

Operators
---------

A subset of Lucene query operators is supported:

- **NOT**: Condition is not true.
- **AND**: Connects two conditions. Both conditions must be true.
- **OR**: Connects two conditions. At least one them must be true.

In the following example log messages are filtered for which :code:`event_id: 1` is true and
:code:`ip_address: 192.168.0.1` is false.
This example is not complete, since rules are specific to processors and require additional options.


..  code-block:: json
    :linenos:
    :caption: Example

    { "filter": "event_id: 1 AND NOT ip_address: 192.168.0.1" }

RegEx-Filter
------------

It is possible to use regex expressions to match values.
To be recognized as a regular expression, the filter field has to start with
:code:`/`.


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'ip_address: /192\.168\.0\..*/'


[Deprecated, but still functional] The field with the regex pattern must be added to the optional field
:code:`regex_fields` in the rule definition.

In the following example the field :code:`ip_address` is defined as regex field.
It would be filtered for log messages in which the value :code:`ip_address` starts with
:code:`192.168.0.`.
This example is not complete, since rules are specific to processors and
require additional options.


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'ip_address: "192\.168\.0\..*"'
    regex_fields:
    - ip_address
"""
import logging
import re
from itertools import chain, zip_longest

# pylint: enable=anomalous-backslash-in-string
from typing import List, Optional, Union

import luqum
from luqum.parser import IllegalCharacterError, ParseSyntaxError, parser
from luqum.tree import (
    AndOperation,
    FieldGroup,
    Group,
    Not,
    OrOperation,
    Phrase,
    Regex,
    SearchField,
    Word,
)

from logprep.filter.expression.filter_expression import (
    Always,
    And,
    Exists,
    FilterExpression,
)
from logprep.filter.expression.filter_expression import Not as NotExpression
from logprep.filter.expression.filter_expression import (
    Null,
    Or,
    RegExFilterExpression,
    SigmaFilterExpression,
    StringFilterExpression,
)

logger = logging.getLogger("LuceneFilter")


class LuceneFilterError(Exception):
    """Base class for LuceneFilter related exceptions."""


class LuceneFilter:
    """A filter that allows using lucene query strings."""

    last_quotation_pattern = re.compile(r'((?:\\)+")$')
    escaping_pattern = re.compile(r'(?:\\)+"')
    end_escaping_pattern = re.compile(r'((?:\\)+"[\s\)]+(?:AND|OR|NOT|$))')

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
        escaped_string = LuceneFilter._add_lucene_escaping(query_string)

        try:
            tree = parser.parse(escaped_string)
            transformer = LuceneTransformer(tree, special_fields)
        except ParseSyntaxError as error:
            msg = f"{error} Expression: '{escaped_string}'" + " - expression not escaped correctly."
            raise LuceneFilterError(msg) from error
        except IllegalCharacterError as error:
            msg = f"{error} in '{escaped_string}'" + " - expression not escaped correctly"
            raise LuceneFilterError(msg) from error

        return transformer.build_filter()

    @staticmethod
    def _add_lucene_escaping(string: str) -> str:
        """Escape double quotes so that the string can be parsed by lucene."""

        string = LuceneFilter._make_uneven_double_quotes_escaping(string)
        string = LuceneFilter._escape_ends_of_expressions(string)
        return string

    @staticmethod
    def _make_uneven_double_quotes_escaping(query_string: str) -> str:
        """Escape double quotes in such a way that the escaping is always uneven.

        It doubles all backslashes and adds one. This allows to revert the operation later on.
        """
        matches = LuceneFilter.escaping_pattern.findall(query_string)
        for idx, match in enumerate(matches):
            cnt_backslashes = len(match) - 1
            if cnt_backslashes > 0:
                matches[idx] = f'{2 * matches[idx][:-1]}\\"'
        split = LuceneFilter.escaping_pattern.split(query_string)
        query_string = "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

        return query_string

    @staticmethod
    def _escape_ends_of_expressions(query_string):
        """Escape double quotes at the end of expressions so that it can be parsed by lucene.

        This is necessary, since double quotes can delimit expressions in the lucene syntax.
        """
        split_string = LuceneFilter.end_escaping_pattern.split(query_string)
        new_string = ""
        for part in [split for split in split_string if split]:
            escaped_quotation = LuceneFilter.end_escaping_pattern.search(part)
            if escaped_quotation and part.startswith("\\"):
                for idx, char in enumerate(part):
                    if char == "\\":
                        new_string += char * 2
                    else:
                        new_string += part[idx:]
                        break
            else:
                new_string += part
        last_quotation = LuceneFilter.last_quotation_pattern.search(new_string)
        if last_quotation:
            cnt_backslashes = len(last_quotation.group()) - 1
            new_end = "\\" * cnt_backslashes * 2 + '"'
            new_string = new_string[: -(cnt_backslashes + 1)] + new_end
        return new_string


class LuceneTransformer:
    """A transformer that converts a luqum tree into a FilterExpression."""

    _special_fields_map = {
        "regex_fields": RegExFilterExpression,
        "sigma_fields": SigmaFilterExpression,
    }

    find_unescaping_quote_pattern = re.compile(r'(?:\\)*"')
    find_unescaping_end_pattern = re.compile(r"(?:\\)*$")

    def __init__(self, tree: luqum.tree, special_fields: dict = None):
        self._tree = tree

        self._special_fields = {}

        special_fields = special_fields if special_fields else {}
        for key in self._special_fields_map:
            self._special_fields[key] = special_fields.get(key) if special_fields.get(key) else []

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
            # pylint: disable=no-value-for-parameter
            return NotExpression(*self._collect_children(tree))
            # pylint: enable=no-value-for-parameter
        if isinstance(tree, Group):
            return self._parse_tree(tree.children[0])
        if isinstance(tree, SearchField):
            if isinstance(tree.expr, FieldGroup):
                self._last_search_field = tree.name
                parsed = self._parse_tree(tree.expr.children[0])
                self._last_search_field = None
                return parsed
            return self._create_field(tree)
        if isinstance(tree, Word):
            if self._last_search_field:
                return self._create_field_group_expression(tree)
            return self._create_value_expression(tree)
        if isinstance(tree, Phrase):
            if self._last_search_field:
                return self._create_field_group_expression(tree)
            return self._create_value_expression(tree)
        raise LuceneFilterError(f'The expression "{str(tree)}" is invalid!')

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
        elif isinstance(tree.expr, Regex):
            key = tree.name.replace("\\", "")
            key = key.split(".")
            if tree.expr.value == "null":
                return Null(key)

            value = self._strip_quote_from_string(tree.expr.value)
            value = self._remove_lucene_escaping(value)
            return self._get_filter_expression_regex(key, value)
        return None

    @staticmethod
    def _check_key_and_modifier(key, value):
        key_and_modifier = key[-1].split("|")
        if len(key_and_modifier) == 2:
            if key_and_modifier[-1] == "re":
                return RegExFilterExpression(key[:-1] + key_and_modifier[:-1], value)
        return None

    def _get_filter_expression(
        self, key: List[str], value
    ) -> Union[RegExFilterExpression, StringFilterExpression]:

        key_and_modifier_check = LuceneTransformer._check_key_and_modifier(key, value)
        if key_and_modifier_check is not None:
            return key_and_modifier_check

        dotted_field = ".".join(key)

        if self._special_fields.items():
            for sf_key, sf_value in self._special_fields.items():
                if sf_value is True or dotted_field in sf_value:
                    if sf_key == "regex_fields":
                        logger.warning(
                            "[Deprecated]: regex_fields are no longer necessary. "
                            "Use Lucene regex annotation."
                        )

                    return self._special_fields_map[sf_key](key, value)

        return StringFilterExpression(key, value)

    def _get_filter_expression_regex(
        self, key: List[str], value
    ) -> Union[RegExFilterExpression, StringFilterExpression]:

        key_and_modifier_check = LuceneTransformer._check_key_and_modifier(key, value)
        if key_and_modifier_check is not None:
            return key_and_modifier_check

        value = value.strip("/")
        return RegExFilterExpression(key, value)

    @staticmethod
    def _create_value_expression(word: luqum.tree) -> Union[Exists, Always]:
        value = word.value.replace("\\", "")
        value = value.split(".")
        if value == ["*"]:
            return Always(True)
        return Exists(value)

    @staticmethod
    def _strip_quote_from_string(string: str) -> str:
        if (string[0] == string[-1]) and (string[0] in ["'", '"']):
            return string[1:-1]
        return string

    @staticmethod
    def _remove_lucene_escaping(string: str) -> str:
        """Remove previously added lucene escaping."""
        string = LuceneTransformer._remove_escaping_from_end_of_expression(string)
        string = LuceneTransformer._remove_uneven_double_quotes_escaping(string)
        string = LuceneTransformer._remove_one_escaping_from_quotes(string)
        return string

    @staticmethod
    def _remove_escaping_from_end_of_expression(string: str) -> str:
        """Remove previously escaping from ends of expressions.

        It halves the amount of all backslashes at the end of expressions.
        This method should be called only on already parsed expressions.
        """
        escaping_end = LuceneTransformer.find_unescaping_end_pattern.search(string)
        if escaping_end is None:
            return string

        backslashes_end_cnt = len(escaping_end.group())
        string = string[: escaping_end.start()] + "\\" * (backslashes_end_cnt // 2)

        escaping_end = LuceneTransformer.find_unescaping_end_pattern.search(string)
        if escaping_end:
            new_escaping = "\\" * ((len(escaping_end.group()) - 1) // 2)
            string = f"{string[:escaping_end.start()]}{new_escaping}"

        return string

    @staticmethod
    def _remove_uneven_double_quotes_escaping(string: str) -> str:
        """Remove previously added lucene escaping that made quotes uneven.

        It removes one backslash and halves the remaining backslashes.
        """
        matches = LuceneTransformer.find_unescaping_quote_pattern.findall(string)
        if matches is None:
            return string

        for idx, match in enumerate(matches):
            cnt_backslashes = len(match) - 1
            if cnt_backslashes >= 3:
                matches[idx] = f'{matches[idx][:(cnt_backslashes - 2) // 2]}\\"'

        split = LuceneTransformer.find_unescaping_quote_pattern.split(string)
        string = "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

        return string

    @staticmethod
    def _remove_one_escaping_from_quotes(string: str) -> str:
        """Remove one backslash from quotes, since it is only used by lucene but not filters."""
        matches = LuceneTransformer.find_unescaping_quote_pattern.findall(string)
        if matches is None:
            return string

        for idx, match in enumerate(matches):
            len_match = len(match) - 1
            if len_match >= 1:
                matches[idx] = matches[idx][1:]

        split = LuceneTransformer.find_unescaping_quote_pattern.split(string)
        string = "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

        return string
