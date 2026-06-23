# pylint: disable=anomalous-backslash-in-string
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-return-statements
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

Range-Filter
------------

It is possible to use range expressions to match integer, floating-point, and
string values. Square brackets include a boundary, while curly brackets exclude
a boundary. String ranges are compared lexicographically.

The lower and upper boundaries of a range must have the same type. Mixed ranges
such as integer-to-float, integer-to-string, or float-to-string are not
supported.


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'age:[18 TO 65]'


The example matches log messages in which the value of :code:`age` is greater
than or equal to :code:`18` and less than or equal to :code:`65`.

Exclusive boundaries are also supported:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'age:{18 TO 65}'


The example matches log messages in which the value of :code:`age` is greater
than :code:`18` and less than :code:`65`.

Floating-point ranges are supported as well:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'temperature:[18.5 TO 25.0]'


String ranges are compared lexicographically:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'status:[alpha TO stable]'


This also allows matching consistently formatted ISO-8601 timestamps as string
ranges:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'timestamp:[2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z]'


The example matches log messages in which the value of :code:`timestamp` is
lexicographically greater than or equal to :code:`2024-01-01T00:00:00Z` and
less than or equal to :code:`2024-12-31T23:59:59Z`.

Range boundaries containing Lucene special characters must be quoted. This is
required, for example, for ISO-8601 timestamps with timezone offsets:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'timestamp:["2024-01-01T00:00:00+01:00" TO "2024-12-31T23:59:59+01:00"]'


Range expressions can also be used within field groups:


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'temperature:([18.5 TO 25.0])'


Open boundaries using :code:`*`, non-finite numeric boundaries, mixed boundary
types, and unquoted boundaries containing Lucene special characters are not
supported.

RegEx-Filter
------------

It is possible to use regex expressions to match values.
To be recognized as a regular expression, the filter field has to start with
:code:`/`.


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'ip_address: /192\.168\.0\..*/'


[Deprecated, but still functional] The field with the regex pattern
must be added to the optional field
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
import math
import re
from itertools import chain, zip_longest
from typing import Sequence

import luqum
from luqum.parser import IllegalCharacterError, ParseSyntaxError, parser
from luqum.tree import (
    AndOperation,
    FieldGroup,
    Group,
    Not,
    OrOperation,
    Phrase,
    Prohibit,
    Range,
    Regex,
    SearchField,
    Word,
)

from logprep.abc.exceptions import LogprepException
from logprep.filter.expression.filter_expression import (
    Always,
    And,
    Exists,
    FilterExpression,
    FloatRangeFilterExpression,
    IntegerRangeFilterExpression,
)
from logprep.filter.expression.filter_expression import Not as NotExpression
from logprep.filter.expression.filter_expression import (
    Null,
    Or,
    RangeBoundary,
    RegExFilterExpression,
    SigmaFilterExpression,
    StringFilterExpression,
    StringRangeFilterExpression,
)
from logprep.util.helper import field_list_to_dotted_field, get_dotted_field_list

# pylint: enable=anomalous-backslash-in-string


logger = logging.getLogger("LuceneFilter")


class LuceneFilterError(LogprepException):
    """Base class for LuceneFilter related exceptions."""


class LuceneFilter:
    """A filter that allows using lucene query strings."""

    last_quotation_pattern = re.compile(r'((?:\\)+")$')
    quote_escaping_pattern = re.compile(r'(?:\\)+"')
    end_escaping_pattern = re.compile(r'((?:\\)+"[\s\)]+(?:AND|OR|NOT|$))')

    @staticmethod
    def create(query_string: str, special_fields: dict | None = None) -> FilterExpression:
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
            tree = parser.parse(escaped_string, lexer=luqum.parser.lexer)
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
        matches = LuceneFilter.quote_escaping_pattern.findall(query_string)
        for idx, match in enumerate(matches):
            cnt_backslashes = len(match) - 1
            if cnt_backslashes > 0:
                matches[idx] = f'{2 * matches[idx][:-1]}\\"'
        split = LuceneFilter.quote_escaping_pattern.split(query_string)
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

    _special_fields_map: dict[str, type[RegExFilterExpression] | type[SigmaFilterExpression]] = {
        "regex_fields": RegExFilterExpression,
        "sigma_fields": SigmaFilterExpression,
    }

    find_unescaping_quote_pattern = re.compile(r'(?:\\)*"')
    find_unescaping_end_pattern = re.compile(r"(?:\\)*\Z")

    def __init__(self, tree: luqum.tree, special_fields: dict | None = None):
        self._tree = tree

        self._special_fields = {}

        special_fields = special_fields if special_fields else {}
        for key in self._special_fields_map:
            self._special_fields[key] = special_fields.get(key, [])

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

        if isinstance(tree, Range):
            if self._last_search_field is None:
                raise LuceneFilterError(f'The expression "{str(tree)}" is invalid!')

            key = get_dotted_field_list(self._last_search_field)
            return self._parse_range(key, tree)

        if isinstance(tree, SearchField):
            if isinstance(tree.expr, FieldGroup):
                self._last_search_field = tree.name
                parsed = self._parse_tree(tree.expr.children[0])
                self._last_search_field = None
                return parsed
            return self._create_field(tree)
        if isinstance(tree, (Word, Phrase, Regex)):
            if self._last_search_field is not None:
                return self._create_field_group_expression(tree, self._last_search_field)
            return self._create_value_expression(tree)
        raise LuceneFilterError(f'The expression "{str(tree)}" is invalid!')

    def _parse_range(self, key: Sequence[str], expr: Range) -> FilterExpression:
        expression = str(expr)
        lower_token, upper_token = expr.children

        include_lower_bound = expression.startswith("[")
        include_upper_bound = expression.endswith("]")

        if not expression.startswith(("[", "{")) or not expression.endswith(("]", "}")):
            raise LuceneFilterError(f'The expression "{expression}" is invalid!')

        lower_value = self._get_range_boundary_value(lower_token)
        upper_value = self._get_range_boundary_value(upper_token)

        for range_parser in (
            self._parse_integer_range,
            self._parse_float_range,
            self._parse_string_range,
        ):
            range_filter_expression = range_parser(
                key,
                lower_value,
                upper_value,
                include_lower_bound,
                include_upper_bound,
                expr,
            )

            if range_filter_expression is not None:
                return range_filter_expression

        raise LuceneFilterError(f'The expression "{expression}" is invalid!')

    @staticmethod
    def _parse_integer_range(
        key: Sequence[str],
        lower_value: str,
        upper_value: str,
        include_lower_bound: bool,
        include_upper_bound: bool,
        expr: Range,
    ) -> IntegerRangeFilterExpression | None:
        """Create an integer range expression if both boundaries are integers."""
        try:
            lower_bound = int(lower_value)
            upper_bound = int(upper_value)
        except ValueError:
            return None

        LuceneTransformer._validate_range_boundaries(lower_bound, upper_bound, expr)

        return IntegerRangeFilterExpression(
            key,
            lower_bound,
            upper_bound,
            include_lower_bound,
            include_upper_bound,
        )

    @staticmethod
    def _parse_float_range(
        key: Sequence[str],
        lower_value: str,
        upper_value: str,
        include_lower_bound: bool,
        include_upper_bound: bool,
        expr: Range,
    ) -> FloatRangeFilterExpression | None:
        """Create a float range expression if both boundaries are finite floats."""
        if LuceneTransformer._is_integer_range_boundary(
            lower_value
        ) or LuceneTransformer._is_integer_range_boundary(upper_value):
            return None

        try:
            lower_bound = float(lower_value)
            upper_bound = float(upper_value)
        except ValueError:
            return None

        expression = str(expr)

        if not math.isfinite(lower_bound) or not math.isfinite(upper_bound):
            raise LuceneFilterError(
                f'The expression "{expression}" is invalid. '
                "Range boundaries must be finite numbers."
            )

        LuceneTransformer._validate_range_boundaries(lower_bound, upper_bound, expr)

        return FloatRangeFilterExpression(
            key,
            lower_bound,
            upper_bound,
            include_lower_bound,
            include_upper_bound,
        )

    @staticmethod
    def _parse_string_range(
        key: Sequence[str],
        lower_value: str,
        upper_value: str,
        include_lower_bound: bool,
        include_upper_bound: bool,
        expr: Range,
    ) -> StringRangeFilterExpression:
        """Create a lexicographic string range expression for non-numeric boundaries."""
        if lower_value == "*" or upper_value == "*":
            raise LuceneFilterError(f'The expression "{expr}" is invalid!')

        if LuceneTransformer._is_numeric_range_boundary(
            lower_value
        ) or LuceneTransformer._is_numeric_range_boundary(upper_value):
            raise LuceneFilterError(f'The expression "{expr}" is invalid!')

        LuceneTransformer._validate_range_boundaries(lower_value, upper_value, expr)

        return StringRangeFilterExpression(
            key,
            lower_value,
            upper_value,
            include_lower_bound,
            include_upper_bound,
        )

    @staticmethod
    def _is_numeric_range_boundary(value: str) -> bool:
        """Return whether a range boundary can be interpreted as a finite number."""
        try:
            numeric_value = float(value)
        except ValueError:
            return False

        return math.isfinite(numeric_value)

    @staticmethod
    def _is_integer_range_boundary(value: str) -> bool:
        """Return whether a range boundary can be interpreted as an integer."""
        try:
            int(value)
        except ValueError:
            return False

        return True

    @staticmethod
    def _is_float_range_boundary(value: str) -> bool:
        """Return whether a range boundary can be interpreted as a finite float."""
        if LuceneTransformer._is_integer_range_boundary(value):
            return False

        try:
            numeric_value = float(value)
        except ValueError:
            return False

        return math.isfinite(numeric_value)

    @staticmethod
    def _get_range_boundary_value(token: luqum.tree) -> str:
        """Return a range boundary as a normalized string.

        Luqum parses a negative boundary such as ``-10`` as
        ``Prohibit(Word("10"))`` instead of ``Word("-10")``. Quoted boundaries are
        parsed as phrases and are required for values containing Lucene special
        characters, such as ISO-8601 timestamps with timezone offsets.
        """

        if isinstance(token, Word):
            return token.value

        if isinstance(token, Phrase):
            return token.value.strip('"')

        if isinstance(token, Prohibit) and len(token.children) == 1:
            child = token.children[0]

            if isinstance(child, Word):
                return f"-{child.value}"

        raise LuceneFilterError(f'The range boundary "{token}" is invalid!')

    @staticmethod
    def _validate_range_boundaries(
        lower_bound: RangeBoundary,
        upper_bound: RangeBoundary,
        expr: Range,
    ) -> None:
        """Validate that the range boundaries form an ascending range.

        Range filter expressions require the lower boundary to be less than or equal
        to the upper boundary. This is independent of whether the boundaries are
        inclusive or exclusive.

        Numeric boundaries are compared numerically. String boundaries are compared
        lexicographically. Without this validation, a reversed range such as
        ``[10 TO 0]`` or ``[foo TO bar]`` would be accepted but could never match
        any value, which would hide a likely configuration error.
        """

        if lower_bound > upper_bound:
            raise LuceneFilterError(
                "The lower range boundary must not exceed " f'the upper range boundary: "{expr}"'
            )

    def _create_field_group_expression(
        self, tree: luqum.tree, dotted_field: str
    ) -> FilterExpression:
        """Creates filter expression that is resulting from a field group.

        Parameters
        ----------
        tree : luqum.tree
            luqum.tree to create field group expression from.
        dotted_field: str
            dotted_field which is treated as the key for the expression.

        Returns
        -------
        FilterExpression
            Parsed filter expression.

        """
        key = get_dotted_field_list(dotted_field)
        value = self._strip_quote_from_string(tree.value)
        value = self._remove_lucene_escaping(value)

        if isinstance(tree, Regex):
            return self._get_filter_expression_regex(key, value)
        return self._get_filter_expression(key, value)

    def _collect_children(self, tree: luqum.tree) -> list[FilterExpression]:
        expressions = []
        for child in tree.children:
            expressions.append(self._parse_tree(child))
        return expressions

    def _create_field(self, tree: luqum.tree) -> FilterExpression:
        key = get_dotted_field_list(tree.name)

        if isinstance(tree.expr, (Phrase, Word)):
            if tree.expr.value == "null":
                return Null(key)

            value = self._strip_quote_from_string(tree.expr.value)
            value = self._remove_lucene_escaping(value)
            return self._get_filter_expression(key, value)

        if isinstance(tree.expr, Regex):
            if tree.expr.value == "null":
                return Null(key)

            value = self._strip_quote_from_string(tree.expr.value)
            value = self._remove_lucene_escaping(value)
            return self._get_filter_expression_regex(key, value)

        if isinstance(tree.expr, Range):
            return self._parse_range(key, tree.expr)

        raise LuceneFilterError(f'The expression "{str(tree)}" is invalid!')

    @staticmethod
    def _check_key_and_modifier(key: Sequence[str], value):
        key_and_modifier = key[-1].split("|")
        if len(key_and_modifier) == 2:
            if key_and_modifier[-1] == "re":
                return RegExFilterExpression([*key[:-1], *key_and_modifier[:-1]], value)
        return None

    def _get_filter_expression(
        self, key: Sequence[str], value
    ) -> RegExFilterExpression | StringFilterExpression | SigmaFilterExpression:

        key_and_modifier_check = LuceneTransformer._check_key_and_modifier(key, value)
        if key_and_modifier_check is not None:
            return key_and_modifier_check

        dotted_field = field_list_to_dotted_field(key)

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
        self, key: Sequence[str], value
    ) -> RegExFilterExpression | StringFilterExpression:

        key_and_modifier_check = LuceneTransformer._check_key_and_modifier(key, value)
        if key_and_modifier_check is not None:
            return key_and_modifier_check

        value = value.strip("/")
        return RegExFilterExpression(key, value)

    @staticmethod
    def _create_value_expression(word: luqum.tree) -> Exists | Always:
        value = get_dotted_field_list(word.value)
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
