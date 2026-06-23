# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-lines
# pylint: disable=missing-function-docstring

import re

import pytest
from pytest import raises

from logprep.filter.expression.filter_expression import (
    Always,
    And,
    Exists,
    Not,
    Null,
    Or,
    RegExFilterExpression,
    StringFilterExpression,
)
from logprep.filter.lucene_filter import (
    LuceneFilter,
    LuceneFilterError,
    LuceneTransformer,
)


@pytest.fixture(
    params=(
        pytest.param(
            "key:{range_expression}",
            id="search-field-range",
        ),
        pytest.param(
            "key:({range_expression})",
            id="field-group-range",
        ),
    )
)
def range_query(request):
    def create_query(range_expression: str) -> str:
        return request.param.format(range_expression=range_expression)

    return create_query


def esc(count: int) -> str:
    """Returns given amount of escaping characters"""
    return count * "\\"


class TestLueceneFilter:
    def test_creates_expected_filter_from_simple_string_query(self):
        lucene_filter = LuceneFilter.create('key: "value"')

        assert lucene_filter == StringFilterExpression(["key"], "value")

    def test_creates_expected_filter_from_simple_expression(self):
        lucene_filter = LuceneFilter.create('(title:"foo bar" AND body:"quick fox") OR title:fox')

        assert lucene_filter == Or(
            And(
                StringFilterExpression(["title"], "foo bar"),
                StringFilterExpression(["body"], "quick fox"),
            ),
            StringFilterExpression(["title"], "fox"),
        )

    def test_created_filter_does_not_match_document_without_requested_key(self):
        lucene_filter = LuceneFilter.create('key: "value"')

        assert not lucene_filter.matches({"not the key": "not the value"})

    def test_created_filter_does_not_match_document_without_wrong_value(self):
        lucene_filter = LuceneFilter.create('key: "value"')

        assert not lucene_filter.matches({"key": "not the value"})

    def test_created_filter_matches_document_with_correct_value(self):
        lucene_filter = LuceneFilter.create('key: "value"')

        assert lucene_filter.matches({"key": "value"})

    def test_created_filter_matches_document_with_special_characters(self):
        assert LuceneFilter.create('key: "\n"').matches({"key": "\n"})
        assert LuceneFilter.create('key: "\t"').matches({"key": "\t"})
        assert LuceneFilter.create('key: "\\a"').matches({"key": "\\a"})
        assert LuceneFilter.create('key: "a\\"').matches({"key": "a\\"})
        assert LuceneFilter.create('key: "\\\\n"').matches({"key": "\\\\n"})
        assert LuceneFilter.create('a\\ key: "x"').matches({"a key": "x"})
        assert LuceneFilter.create('a\\\tkey: "x"').matches({"a\tkey": "x"})
        assert LuceneFilter.create('key\\\\n: "x"').matches({"key\\n": "x"})

    @pytest.mark.xfail(reason="luqum disallows triple escapes in values", strict=True)
    def test_created_filter_matches_document_with_triple_escape(self):
        assert LuceneFilter.create('key: "\\\n"')

    @pytest.mark.xfail(reason="luqum interprets newlines in keys as separators", strict=True)
    def test_created_filter_matches_document_with_newline_in_key(self):
        assert LuceneFilter.create('k\ney: "x"')

    @pytest.mark.xfail(reason="luqum does not allow escaping newlines in keys", strict=True)
    def test_created_filter_matches_document_with_escaped_newline_in_key(self):
        assert LuceneFilter.create('a\\\nkey: "x"').matches({"a\nkey": "x"})

    @pytest.mark.xfail(reason="luqum interprets unquoted tabs as separators", strict=True)
    def test_created_filter_matches_document_with_tab_in_key(self):
        assert LuceneFilter.create('k\tey: "x"')

    def test_created_filter_matches_document_with_parenthesis(self):
        lucene_filter = LuceneFilter.create('(key: "value")')

        assert lucene_filter.matches({"key": "value"})

    def test_created_and_filter_matches_or_value(self):
        lucene_filter = LuceneFilter.create('key: ("value" OR "value2")')

        assert not lucene_filter.matches({})
        assert not lucene_filter.matches({"key": "wrong value"})

        assert lucene_filter.matches({"key": "value"})
        assert lucene_filter.matches({"key": "value2"})

    def test_created_and_filter_matches_only_document_with_both_correct_value(self):
        lucene_filter = LuceneFilter.create('key: "value" AND key2: "value2"')

        assert not lucene_filter.matches({})
        assert not lucene_filter.matches({"key": "value"})
        assert not lucene_filter.matches({"key2": "value2"})
        assert not lucene_filter.matches({"key": "wrong value", "key2": "value2"})
        assert not lucene_filter.matches({"key": "value", "key2": "wrong value"})
        assert not lucene_filter.matches({"key": "wrong value", "key2": "wrong value"})

        assert lucene_filter.matches({"key": "value", "key2": "value2"})

    def test_created_or_filter_matches_any_document_with_one_correct_value(self):
        lucene_filter = LuceneFilter.create('key: "value" OR key2: "value2"')

        assert not lucene_filter.matches({})
        assert not lucene_filter.matches({"key": "wrong value", "key2": "wrong value"})

        assert lucene_filter.matches({"key": "value"})
        assert lucene_filter.matches({"key2": "value2"})
        assert lucene_filter.matches({"key": "wrong value", "key2": "value2"})
        assert lucene_filter.matches({"key": "value", "key2": "wrong value"})
        assert lucene_filter.matches({"key": "value", "key2": "value2"})

    def test_creates_expected_filter_from_query_tagged_as_regex(self):
        lucene_filter = LuceneFilter.create(
            'key: "value"', special_fields={"regex_fields": ["key"]}
        )

        assert lucene_filter == RegExFilterExpression(["key"], "value")

    def test_creates_expected_filter_from_query_tagged_as_regex_with_field_group(self):
        lucene_filter = LuceneFilter.create(
            'key: ("value" OR "value2")', special_fields={"regex_fields": ["key"]}
        )

        assert lucene_filter == Or(
            RegExFilterExpression(["key"], "value"), RegExFilterExpression(["key"], "value2")
        )

    def test_creates_expected_filter_from_regex_query(self):
        lucene_filter = LuceneFilter.create(
            'key: ".*value.*"', special_fields={"regex_fields": ["key"]}
        )

        assert lucene_filter == RegExFilterExpression(["key"], ".*value.*")

    def test_creates_expected_filter_from_regex_query_with_dot_partially(self):
        lucene_filter = LuceneFilter.create(
            'event.key: "value"', special_fields={"regex_fields": ["key"]}
        )

        assert lucene_filter == StringFilterExpression(["event", "key"], "value")

    def test_creates_expected_filter_from_regex_query_with_dot(self):
        lucene_filter = LuceneFilter.create(
            'event.key: ".*value.*"', special_fields={"regex_fields": ["event.key"]}
        )

        assert lucene_filter == RegExFilterExpression(["event", "key"], ".*value.*")

    def test_creates_string_filter_without_matching_regex_key(self):
        lucene_filter = LuceneFilter.create(
            'key: ".*value.*"', special_fields={"regex_fields": ["i_do_not_match"]}
        )

        assert lucene_filter == StringFilterExpression(["key"], ".*value.*")

    def test_creates_string_filter_with_two_matching_regex_keys_of_two(self):
        lucene_filter = LuceneFilter.create(
            'regex_key_one: ".*value.*" AND regex_key_two: ".*value.*"',
            special_fields={"regex_fields": ["regex_key_one", "regex_key_two"]},
        )

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            RegExFilterExpression(["regex_key_two"], ".*value.*"),
        )

    def test_creates_string_filter_with_one_matching_and_one_missmatching_regex_key_of_two(self):
        lucene_filter = LuceneFilter.create(
            'regex_key_one: ".*value.*" AND key_two: "value"',
            special_fields={"regex_fields": ["regex_key_one", "i_dont_exist"]},
        )

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            StringFilterExpression(["key_two"], "value"),
        )

    def test_creates_string_filter_with_one_matching_regex_key_of_two(self):
        lucene_filter = LuceneFilter.create(
            'regex_key: ".*value.*" AND string_key: "value"',
            special_fields={"regex_fields": ["regex_key"]},
        )

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key"], ".*value.*"),
            StringFilterExpression(["string_key"], "value"),
        )

    def test_creates_string_filter_with_pipe_regex(self):
        lucene_filter = LuceneFilter.create('regex_key|re: ".*value.*" AND string_key: "value"')

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key"], ".*value.*"),
            StringFilterExpression(["string_key"], "value"),
        )

    def test_does_not_create_null_filter_with_string(self):
        lucene_filter = LuceneFilter.create('null_key: "null"')

        assert lucene_filter == StringFilterExpression(["null_key"], "null")

    def test_creates_null_filter(self):
        lucene_filter = LuceneFilter.create("null_key: null")

        assert lucene_filter == Null(["null_key"])

    def test_creates_null_filter_dotted(self):
        lucene_filter = LuceneFilter.create("something.null_key: null")

        assert lucene_filter == Null(["something", "null_key"])

    def test_creates_filter_escaped(self):
        lucene_filter = LuceneFilter.create('a\\ key\\(: "value"')

        assert lucene_filter == StringFilterExpression(["a key("], "value")

    def test_creates_filter_escaped_with_regex_tag(self):
        lucene_filter = LuceneFilter.create('a\\ key\\(|re: "value"')

        assert lucene_filter == RegExFilterExpression(["a key("], "value")

    def test_creates_filter_escaped_with_dotted_regex_tag(self):
        lucene_filter = LuceneFilter.create('key.a\\ subkey\\(|re: "value"')

        assert lucene_filter == RegExFilterExpression(["key", "a subkey("], "value")

    def test_creates_filter_not_escaped_raises_exception(self):
        with raises(LuceneFilterError):
            LuceneFilter.create('a key(: "value"')

    def test_creates_filter_match_all(self):
        lucene_filter = LuceneFilter.create("*")
        assert lucene_filter == Always(True)

    def test_creates_filter_exists(self):
        lucene_filter = LuceneFilter.create("foo")
        assert lucene_filter == Exists(["foo"])

    def test_creates_filter_not_exists(self):
        lucene_filter = LuceneFilter.create("NOT foo")
        assert lucene_filter == Not(Exists(["foo"]))

    escape_ends_of_expressions_test_cases = [
        pytest.param("", "", id="Empty string"),
        pytest.param("foo bar baz", "foo bar baz", id="No escaping"),
        pytest.param("\\foo \\bar \\baz", "\\foo \\bar \\baz", id="Escaped words"),
        pytest.param('"', '"', id="One quotation"),
        pytest.param('\\"', '\\\\"', id="One single escaped quotation (1->2)"),
        pytest.param('\\\\"', '\\\\\\\\"', id="One double escaped quotation (2->4)"),
        pytest.param('\\\\\\"', '\\\\\\\\\\\\"', id="One triple escaped quotation (3->6)"),
        pytest.param('\\"foo\\"', '\\"foo\\\\"', id="Escaped not last"),
        pytest.param('""', '""', id="Two quotations"),
        pytest.param('\\"\\"\\"', '\\"\\"\\\\"', id="Three single escaped quotation"),
        pytest.param('\\\\"\\"', '\\\\"\\\\"', id="One double escaped quotation at beginning"),
        pytest.param('\\" AND', '\\\\" AND', id="Quotation ends with AND"),
        pytest.param('\\" OR', '\\\\" OR', id="Quotation ends with OR"),
        pytest.param('\\" NOT', '\\\\" NOT', id="Quotation ends with NOT"),
        pytest.param('\\" foo', '\\" foo', id="Quotation doesn't end with AND/OR/NOT/$"),
        pytest.param('\\") AND', '\\\\") AND', id="Quotation with parenthesis ends with AND"),
        pytest.param('\\") OR', '\\\\") OR', id="Quotation with parenthesis ends with OR"),
        pytest.param('\\") NOT', '\\\\") NOT', id="Quotation with parenthesis ends with NOT"),
        pytest.param(
            '\\") foo', '\\") foo', id="Quotation with parenthesis doesn't end with AND/OR/NOT/$"
        ),
        pytest.param('\\"foo AND', '\\"foo AND', id="Word between quotation and AND"),
        pytest.param('\\"foo OR', '\\"foo OR', id="Word between quotation and OR"),
        pytest.param('\\"foo NOT', '\\"foo NOT', id="Word between quotation and NOT"),
        pytest.param("\\", "\\", id="One escape character"),
        pytest.param("\\\\", "\\\\", id="Two escape characters"),
    ]

    @pytest.mark.parametrize(
        "input_string, escaped_string",
        escape_ends_of_expressions_test_cases,
    )
    def test_escape_ends_of_expressions(self, input_string, escaped_string):
        result = LuceneFilter._escape_ends_of_expressions(input_string)
        assert result == escaped_string

    unescape_ends_of_expressions_test_cases = [
        pytest.param("", "", id="Empty string"),
        pytest.param("foo bar baz", "foo bar baz", id="No escaping"),
        pytest.param("\\foo \\bar \\baz", "\\foo \\bar \\baz", id="Escaped words"),
        pytest.param('"', '"', id="One quotation"),
        pytest.param('""', '""', id="Two quotations"),
        pytest.param(f"{esc(6)}", f"{esc(1)}", id="Unescape (6->3->1)"),
        pytest.param('\\"', '\\"', id="Don't unescape if quotation (1->1)"),
        pytest.param(f"{esc(10)}", f"{esc(2)}", id="Unescape (10->5->2)"),
        pytest.param(f"{esc(14)}", f"{esc(3)}", id="Four escaped quotations (14->7->3)"),
        pytest.param(f'\\"foo{esc(6)}', '\\"foo\\', id="Escaped not last"),
        pytest.param(f'\\"\\"{esc(6)}', '\\"\\"\\', id="Two single escaped quotation"),
        pytest.param(
            f'{esc(2)}"{esc(6)}',
            f'{esc(2)}"{esc(1)}',
            id="One double escaped quotation at beginning",
        ),
    ]

    @pytest.mark.parametrize(
        "input_string, unescaped_string",
        unescape_ends_of_expressions_test_cases,
    )
    def test_remove_escaping_from_end_of_expression(self, input_string, unescaped_string):
        result = LuceneTransformer._remove_escaping_from_end_of_expression(input_string)
        assert result == unescaped_string

    uneven_double_quotes_escaping_test_cases = [
        pytest.param("", "", id="Empty string"),
        pytest.param("foo bar baz", "foo bar baz", id="No escaping"),
        pytest.param("\\foo \\bar \\baz", "\\foo \\bar \\baz", id="Escaped words"),
        pytest.param('"', '"', id="One quotation"),
        pytest.param('""', '""', id="Two quotations"),
        pytest.param('\\"', '\\\\\\"', id="One single escaped quotation (1->3)"),
        pytest.param('\\\\"', '\\\\\\\\\\"', id="One double escaped quotation (2->5)"),
        pytest.param('\\\\\\"', '\\\\\\\\\\\\\\"', id="One triple escaped quotation (3->7)"),
        pytest.param('\\"foo\\"', '\\\\\\"foo\\\\\\"', id="Escaped not last (1->3)"),
        pytest.param(
            '\\"\\"\\"', '\\\\\\"\\\\\\"\\\\\\"', id="Three single escaped quotation (1->3)"
        ),
        pytest.param(
            '\\\\"\\"', '\\\\\\\\\\"\\\\\\"', id="One double escaped quotation at beginning"
        ),
        pytest.param('\\" AND', '\\\\\\" AND', id="Quotation ends with AND"),
        pytest.param('\\" OR', '\\\\\\" OR', id="Quotation ends with OR"),
        pytest.param('\\" NOT', '\\\\\\" NOT', id="Quotation ends with NOT"),
        pytest.param('\\" foo', '\\\\\\" foo', id="Quotation doesn't end with AND/OR/NOT/$"),
        pytest.param('\\") AND', '\\\\\\") AND', id="Quotation with parenthesis ends with AND"),
        pytest.param('\\") OR', '\\\\\\") OR', id="Quotation with parenthesis ends with OR"),
        pytest.param('\\") NOT', '\\\\\\") NOT', id="Quotation with parenthesis ends with NOT"),
        pytest.param(
            '\\") foo', '\\\\\\") foo', id="Quotation with parenthesis doesn't end with keyword"
        ),
        pytest.param('\\"foo AND', '\\\\\\"foo AND', id="Word between quotation and AND"),
        pytest.param('\\"foo OR', '\\\\\\"foo OR', id="Word between quotation and OR"),
        pytest.param('\\"foo NOT', '\\\\\\"foo NOT', id="Word between quotation and NOT"),
        pytest.param("\\", "\\", id="One escape character"),
        pytest.param("\\\\", "\\\\", id="Two escape characters"),
    ]

    @pytest.mark.parametrize(
        "input_string, escaped_string",
        uneven_double_quotes_escaping_test_cases,
    )
    def test_make_uneven_double_quotes_escaping(self, input_string, escaped_string):
        result = LuceneFilter._make_uneven_double_quotes_escaping(input_string)
        assert result == escaped_string

    @pytest.mark.parametrize(
        "input_string, escaped_string",
        uneven_double_quotes_escaping_test_cases,
    )
    def test_remove_uneven_double_quotes_escaping(self, input_string, escaped_string):
        result = LuceneTransformer._remove_uneven_double_quotes_escaping(escaped_string)
        assert result == input_string

    add_escaping_test_cases = [
        pytest.param("", "", id="Empty string"),
        pytest.param("foo bar baz", "foo bar baz", id="No escaping"),
        pytest.param("\\foo \\bar \\baz", "\\foo \\bar \\baz", id="Escaped words"),
        pytest.param('"', '"', id="One quotation"),
        pytest.param('\\"', f'{esc(6)}"', id="One single escaped quotation (1->3->6)"),
        pytest.param('\\\\"', f'{esc(10)}"', id="One double escaped quotation (2->5->10)"),
        pytest.param('\\\\\\"', f'{esc(14)}"', id="One triple escaped quotation (3->7->14)"),
        pytest.param('\\"foo\\"', f'{esc(3)}"foo{esc(6)}"', id="Escaped not last"),
        pytest.param('""', '""', id="Two quotations"),
        pytest.param(
            '\\"\\"\\"', f'{esc(3)}"{esc(3)}"{esc(6)}"', id="Three single escaped quotation"
        ),
        pytest.param(
            '\\\\"\\"', f'{esc(5)}"{esc(6)}"', id="One double escaped quotation at beginning"
        ),
        pytest.param('\\" AND', f'{esc(6)}" AND', id="Quotation ends with AND"),
        pytest.param('\\" OR', f'{esc(6)}" OR', id="Quotation ends with OR"),
        pytest.param('\\" NOT', f'{esc(6)}" NOT', id="Quotation ends with NOT"),
        pytest.param('\\" foo', f'{esc(3)}" foo', id="Quotation doesn't end with AND/OR/NOT/$"),
        pytest.param('\\") AND', f'{esc(6)}") AND', id="Quotation with parenthesis ends with AND"),
        pytest.param('\\") OR', f'{esc(6)}") OR', id="Quotation with parenthesis ends with OR"),
        pytest.param('\\") NOT', f'{esc(6)}") NOT', id="Quotation with parenthesis ends with NOT"),
        pytest.param(
            '\\") foo',
            f'{esc(3)}") foo',
            id="Quotation with parenthesis doesn't end with AND/OR/NOT/$",
        ),
        pytest.param('\\"foo AND', f'{esc(3)}"foo AND', id="Word between quotation and AND"),
        pytest.param('\\"foo OR', f'{esc(3)}"foo OR', id="Word between quotation and OR"),
        pytest.param('\\"foo NOT', f'{esc(3)}"foo NOT', id="Word between quotation and NOT"),
        pytest.param("\\", "\\", id="One escape character"),
        pytest.param("\\\\", "\\\\", id="Two escape characters"),
    ]

    @pytest.mark.parametrize(
        "input_string, escaped_string",
        add_escaping_test_cases,
    )
    def test_add_lucene_escaping(self, input_string, escaped_string):
        result = LuceneFilter._add_lucene_escaping(input_string)
        assert result == escaped_string

    remove_one_escaping_from_quotes = [
        pytest.param("", "", id="Empty string"),
        pytest.param("foo bar baz", "foo bar baz", id="No escaping"),
        pytest.param("\\foo \\bar \\baz", "\\foo \\bar \\baz", id="Escaped words"),
        pytest.param('"', '"', id="One quotation"),
        pytest.param('""', '""', id="Two quotations"),
        pytest.param("\\", "\\", id="One escape at the end (1->1)"),
        pytest.param("\\\\", "\\\\", id="Two escapes at the end (2->2)"),
        pytest.param("\\\\\\", "\\\\\\", id="Three escapes at the end (3->2)"),
        pytest.param('\\"', '"', id="One single escaped quotation (1->0)"),
        pytest.param('\\\\"', '\\"', id="One double escaped quotation (2->1)"),
        pytest.param('\\\\\\"', '\\\\"', id="One triple escaped quotation (3->2)"),
        pytest.param('\\"foo\\"', '"foo"', id="Escaped not last"),
        pytest.param('\\"\\"\\"', '"""', id="Three single escaped quotation"),
        pytest.param('\\" AND', '" AND', id="Quotation ends with AND"),
        pytest.param('\\" OR', '" OR', id="Quotation ends with OR"),
        pytest.param('\\" NOT', '" NOT', id="Quotation ends with NOT"),
    ]

    @pytest.mark.parametrize(
        "input_string, escaped_string",
        remove_one_escaping_from_quotes,
    )
    def test_remove_one_escaping_from_quotes(self, input_string, escaped_string):
        result = LuceneTransformer._remove_one_escaping_from_quotes(input_string)
        assert result == escaped_string

    remove_escaping_test_cases = [
        (case, expected, test_input) for case, test_input, expected in add_escaping_test_cases
    ]

    remove_escaping_test_cases_end_escaping = [
        pytest.param('"', '"', id="One quote character"),
        pytest.param(esc(1), esc(0), id="One escape character"),
        pytest.param(esc(6), esc(1), id="Six escape characters"),
        pytest.param(esc(10), esc(2), id="Ten escape characters"),
        pytest.param(f'{esc(1)}"', f'{esc(0)}"', id="One escape character with quotation after"),
        pytest.param(f'{esc(6)}"', f'{esc(2)}"', id="Six escape characters with quotation after"),
        pytest.param(f'{esc(10)}"', f'{esc(4)}"', id="Ten escape characters with quotation after"),
        pytest.param(
            f'{esc(12)}"', f'{esc(5)}"', id="Twelve escape characters with quotation after"
        ),
        pytest.param(f'"{esc(1)}', f'"{esc(0)}', id="One escape character with quotation before"),
        pytest.param(f'"{esc(6)}', f'"{esc(1)}', id="Two escape characters with quotation before"),
        pytest.param(
            f'"{esc(10)}', f'"{esc(2)}', id="Four escape characters with quotation before"
        ),
        pytest.param(
            f'{esc(1)}"x', f'{esc(0)}"x', id="One escape character with quotation not last"
        ),
        pytest.param(
            f'{esc(6)}"x', f'{esc(2)}"x', id="Two escape characters with quotation ot last"
        ),
        pytest.param(
            f'{esc(10)}"x', f'{esc(4)}"x', id="Four escape characters with quotation ot last"
        ),
    ]

    @pytest.mark.parametrize(
        "escaped_string, unescaped_string",
        remove_escaping_test_cases_end_escaping,
    )
    def test_remove_lucene_escaping(self, escaped_string, unescaped_string):
        result = LuceneTransformer._remove_lucene_escaping(escaped_string)
        assert result == unescaped_string

    @pytest.mark.parametrize(
        "input_str, cleaned_str",
        [
            pytest.param("", "", id="Empty string"),
            pytest.param("\\", "\\", id="No escaping"),
            pytest.param("\\foo \\bar", "\\foo \\bar", id="Escaped words"),
            pytest.param('\\"', '"', id="One single escaped quotation"),
            pytest.param('\\\\\\"', '\\\\"', id="One triple escaped quotation"),
            pytest.param("\\foo\\bar\\", "\\foo\\bar\\", id="Path"),
            pytest.param("\\\\foo\\\\bar\\\\", "\\\\foo\\\\bar\\\\", id="Escaped path"),
            pytest.param('\\"\\', '"\\', id="One double escaped quotation at end"),
        ],
    )
    def test_create_filter_success(self, input_str, cleaned_str):
        test_filter = LuceneFilter.create(f'foo: "{input_str}"')
        assert test_filter == StringFilterExpression(["foo"], cleaned_str)

    create_filter_fail_test_cases = [
        pytest.param(
            '"',
            "Illegal character '\"' at position 7 in 'foo: \"\"\"' - "
            + "expression not escaped correctly",
            id="One not escaped quotation",
        ),
        pytest.param(
            '""', 'The expression "foo: """"" is invalid!', id="Two not escaped quotation"
        ),
        pytest.param(
            '" bar',
            'The expression "foo: "" bar"" is invalid!',
            id="Quotation doesn't end with AND/OR/NOT/$",
        ),
    ]

    @pytest.mark.parametrize("input_str, message", create_filter_fail_test_cases)
    def test_create_filter_error(self, input_str, message):
        with raises(LuceneFilterError, match=re.escape(message)):
            LuceneFilter.create(f'foo: "{input_str}"')

    def test_creates_lucene_compliance_filter_two_matching_regex_keys_of_two(self):
        lucene_filter = LuceneFilter.create(
            "regex_key_one: /.*value.*/ AND regex_key_two: /.*value.*/",
        )

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            RegExFilterExpression(["regex_key_two"], ".*value.*"),
        )

    def test_creates_StringFilter_not_Regex(self):
        lucene_filter = LuceneFilter.create(
            'regex_key_one: "/.*value.*/"',
        )

        assert lucene_filter == StringFilterExpression(["regex_key_one"], "/.*value.*/")

    def test_new_lucene_compliance(self):
        lucene_filter = LuceneFilter.create("regex_key_one:/.*value.*/")

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], ".*value.*")

    def test_creates_lucene_compliance_filter_one_matching_one_missmatch_regex_key_of_two(self):
        lucene_filter = LuceneFilter.create(
            'regex_key_one:/.*value.*/ AND key_two: "/.*value.*/"',
        )

        assert lucene_filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            StringFilterExpression(["key_two"], "/.*value.*/"),
        )

    def test_new_lucene_compliance_double_escape(self):
        lucene_filter = LuceneFilter.create("regex_key_one:/\\/.*value.*/")

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], r"\/.*value.*")

    def test_new_lucene_compliance_single_escape(self):
        lucene_filter = LuceneFilter.create(r"regex_key_one:/\/.*value.*/")

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], r"\/.*value.*")

    def test_new_lucene_compliance_parentheses(self):
        lucene_filter = LuceneFilter.create("regex_key_one:(/.*value.*/)")

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], ".*value.*")

    def test_creates_lucene_compliance_filter_parentheses_or_both_regex(self):
        lucene_filter = LuceneFilter.create("regex_key_one: (/.*value_one.*/ OR /.*value_two.*/)")

        assert lucene_filter == Or(
            RegExFilterExpression(["regex_key_one"], ".*value_one.*"),
            RegExFilterExpression(["regex_key_one"], ".*value_two.*"),
        )

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[0 TO 10]",
                (0, 5, 10),
                (-1, 11),
                id="positive-integer-range-including-boundaries",
            ),
            pytest.param(
                "[-10 TO -1]",
                (-10, -5, -1),
                (-11, 0),
                id="negative-integer-range",
            ),
            pytest.param(
                "[-10 TO 10]",
                (-10, 0, 10),
                (-11, 11),
                id="integer-range-across-zero",
            ),
            pytest.param(
                "[0 TO 0]",
                (0,),
                (-1, 1),
                id="single-integer-value-range",
            ),
            pytest.param(
                "[2147483647 TO 2147483648]",
                (2147483647, 2147483648),
                (2147483646, 2147483649),
                id="integer-values-above-32-bit-boundary",
            ),
            pytest.param(
                "[-9223372036854775809 TO -9223372036854775808]",
                (-9223372036854775809, -9223372036854775808),
                (-9223372036854775810, -9223372036854775807),
                id="integer-values-below-64-bit-boundary",
            ),
        ),
    )
    def test_created_integer_range_filter_matches_values_inside_inclusive_range(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[0.1 TO 8.5]",
                (0.1, 5.0, 8.5),
                (0.099, 8.501),
                id="positive-float-range-including-boundaries",
            ),
            pytest.param(
                "[-8.5 TO -0.1]",
                (-8.5, -4.2, -0.1),
                (-8.501, 0),
                id="negative-float-range",
            ),
            pytest.param(
                "[-1.5 TO 1.5]",
                (-1.5, 0.0, 1.5),
                (-1.501, 1.501),
                id="float-range-across-zero",
            ),
            pytest.param(
                "[1.5 TO 1.5]",
                (1.5,),
                (1.499, 1.501),
                id="single-float-value-range",
            ),
            pytest.param(
                "[1e-3 TO 1e3]",
                (0.001, 1.0, 1000.0),
                (0.0009, 1000.1),
                id="scientific-notation",
            ),
            pytest.param(
                "[-1.0e3 TO -1.0e-3]",
                (-1000.0, -1.0, -0.001),
                (-1000.1, 0.0),
                id="negative-scientific-notation",
            ),
        ),
    )
    def test_created_float_range_filter_matches_values_inside_inclusive_range(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[bar TO foo]",
                ("bar", "baz", "foo"),
                ("aaa", "zoo"),
                id="string-range-including-boundaries",
            ),
            pytest.param(
                "[a TO z]",
                ("a", "m", "z"),
                ("A", "zz"),
                id="single-character-string-range",
            ),
            pytest.param(
                "[apple TO banana]",
                ("apple", "apricot", "banana"),
                ("aardvark", "carrot"),
                id="word-string-range",
            ),
            pytest.param(
                "[abc TO abc]",
                ("abc",),
                ("abb", "abd"),
                id="single-string-value-range",
            ),
            pytest.param(
                "[A TO z]",
                ("A", "Z", "a", "m", "z"),
                ("0", "zz"),
                id="mixed-case-string-range",
            ),
        ),
    )
    def test_created_string_range_filter_matches_values_inside_lexicographic_range(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[0 TO 10]",
                (0, 5, 10),
                (-1, 11),
                id="integer-inclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "{0 TO 10}",
                (1, 5, 9),
                (-1, 0, 10, 11),
                id="integer-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{0 TO 10]",
                (1, 5, 10),
                (-1, 0, 11),
                id="integer-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[0 TO 10}",
                (0, 5, 9),
                (-1, 10, 11),
                id="integer-inclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{-10 TO -1}",
                (-9, -5, -2),
                (-10, -1, 0),
                id="negative-integer-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{-10 TO -1]",
                (-9, -5, -1),
                (-10, 0),
                id="negative-integer-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[-10 TO -1}",
                (-10, -5, -2),
                (-11, -1, 0),
                id="negative-integer-inclusive-lower-exclusive-upper",
            ),
        ),
    )
    def test_created_integer_range_filter_respects_boundary_inclusiveness(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[0.1 TO 8.5]",
                (0.1, 5.0, 8.5),
                (0.099, 8.501),
                id="float-inclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "{0.1 TO 8.5}",
                (0.101, 5.0, 8.499),
                (0.1, 8.5),
                id="float-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{0.1 TO 8.5]",
                (0.101, 5.0, 8.5),
                (0.1, 8.501),
                id="float-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[0.1 TO 8.5}",
                (0.1, 5.0, 8.499),
                (0.099, 8.5),
                id="float-inclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{-8.5 TO -0.1}",
                (-8.499, -4.2, -0.101),
                (-8.5, -0.1, 0),
                id="negative-float-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{-8.5 TO -0.1]",
                (-8.499, -4.2, -0.1),
                (-8.5, 0),
                id="negative-float-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[-8.5 TO -0.1}",
                (-8.5, -4.2, -0.101),
                (-8.501, -0.1, 0),
                id="negative-float-inclusive-lower-exclusive-upper",
            ),
        ),
    )
    def test_created_float_range_filter_respects_boundary_inclusiveness(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[bar TO foo]",
                ("bar", "baz", "foo"),
                ("aaa", "zoo"),
                id="string-inclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "{bar TO foo}",
                ("baz", "faa"),
                ("bar", "foo", "aaa", "zoo"),
                id="string-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{bar TO foo]",
                ("baz", "foo"),
                ("bar", "aaa", "zoo"),
                id="string-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[bar TO foo}",
                ("bar", "baz"),
                ("foo", "aaa", "zoo"),
                id="string-inclusive-lower-exclusive-upper",
            ),
        ),
    )
    def test_created_string_range_filter_respects_boundary_inclusiveness(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_value", "wrong_values"),
        (
            pytest.param(
                "[0 TO 10]",
                5,
                ("5", 5.0, object()),
                id="integer-range-does-not-match-non-integer-document-values",
            ),
            pytest.param(
                "[0.1 TO 8.5]",
                5.0,
                ("5.0", 5, object()),
                id="float-range-does-not-match-non-float-document-values",
            ),
            pytest.param(
                "[bar TO foo]",
                "baz",
                (5, 5.0, object()),
                id="string-range-does-not-match-non-string-document-values",
            ),
        ),
    )
    def test_created_range_filter_does_not_match_wrong_value_type(
        self,
        range_query,
        range_expression,
        matching_value,
        wrong_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        assert lucene_filter.matches({"key": matching_value})

        for wrong_value in wrong_values:
            assert not lucene_filter.matches({"key": wrong_value})

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "{0 TO 0}",
                id="exclusive-integer-range-with-equal-boundaries",
            ),
            pytest.param(
                "{0 TO 0]",
                id="exclusive-lower-integer-range-with-equal-boundaries",
            ),
            pytest.param(
                "[0 TO 0}",
                id="exclusive-upper-integer-range-with-equal-boundaries",
            ),
            pytest.param(
                "{1.5 TO 1.5}",
                id="exclusive-float-range-with-equal-boundaries",
            ),
            pytest.param(
                "{1.5 TO 1.5]",
                id="exclusive-lower-float-range-with-equal-boundaries",
            ),
            pytest.param(
                "[1.5 TO 1.5}",
                id="exclusive-upper-float-range-with-equal-boundaries",
            ),
            pytest.param(
                "{abc TO abc}",
                id="exclusive-string-range-with-equal-boundaries",
            ),
            pytest.param(
                "{abc TO abc]",
                id="exclusive-lower-string-range-with-equal-boundaries",
            ),
            pytest.param(
                "[abc TO abc}",
                id="exclusive-upper-string-range-with-equal-boundaries",
            ),
        ),
    )
    def test_created_exclusive_range_with_equal_boundaries_matches_no_value(
        self,
        range_query,
        range_expression,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        assert not lucene_filter.matches({"key": 0})
        assert not lucene_filter.matches({"key": 1.5})
        assert not lucene_filter.matches({"key": "abc"})

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[0 TO 10]",
                id="integer-inclusive-range",
            ),
            pytest.param(
                "{0 TO 10}",
                id="integer-exclusive-range",
            ),
            pytest.param(
                "{0 TO 10]",
                id="integer-exclusive-inclusive-range",
            ),
            pytest.param(
                "[0 TO 10}",
                id="integer-inclusive-exclusive-range",
            ),
            pytest.param(
                "[-1.5 TO 1.5]",
                id="float-inclusive-range",
            ),
            pytest.param(
                "{-1.5 TO 1.5}",
                id="float-exclusive-range",
            ),
            pytest.param(
                "{-1.5 TO 1.5]",
                id="float-exclusive-inclusive-range",
            ),
            pytest.param(
                "[-1.5 TO 1.5}",
                id="float-inclusive-exclusive-range",
            ),
            pytest.param(
                "[bar TO foo]",
                id="string-inclusive-range",
            ),
            pytest.param(
                "{bar TO foo}",
                id="string-exclusive-range",
            ),
            pytest.param(
                "{bar TO foo]",
                id="string-exclusive-inclusive-range",
            ),
            pytest.param(
                "[bar TO foo}",
                id="string-inclusive-exclusive-range",
            ),
        ),
    )
    def test_created_range_filter_does_not_match_missing_field(
        self,
        range_query,
        range_expression,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        assert not lucene_filter.matches({})
        assert not lucene_filter.matches({"other_key": 5})

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[10 TO 0]",
                id="reversed-inclusive-integer-range",
            ),
            pytest.param(
                "{10 TO 0}",
                id="reversed-exclusive-integer-range",
            ),
            pytest.param(
                "{10 TO 0]",
                id="reversed-exclusive-inclusive-integer-range",
            ),
            pytest.param(
                "[10 TO 0}",
                id="reversed-inclusive-exclusive-integer-range",
            ),
            pytest.param(
                "[10.5 TO -1.5]",
                id="reversed-inclusive-float-range",
            ),
            pytest.param(
                "{10.5 TO -1.5}",
                id="reversed-exclusive-float-range",
            ),
            pytest.param(
                "{10.5 TO -1.5]",
                id="reversed-exclusive-inclusive-float-range",
            ),
            pytest.param(
                "[10.5 TO -1.5}",
                id="reversed-inclusive-exclusive-float-range",
            ),
            pytest.param(
                "[foo TO bar]",
                id="reversed-inclusive-string-range",
            ),
            pytest.param(
                "{foo TO bar}",
                id="reversed-exclusive-string-range",
            ),
            pytest.param(
                "{foo TO bar]",
                id="reversed-exclusive-inclusive-string-range",
            ),
            pytest.param(
                "[foo TO bar}",
                id="reversed-inclusive-exclusive-string-range",
            ),
        ),
    )
    def test_create_rejects_range_with_reversed_boundaries(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(
                "The lower range boundary must not exceed "
                f'the upper range boundary: "{range_expression}"'
            ),
        ):
            LuceneFilter.create(range_query(range_expression))

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[0 TO 10.5]",
                id="integer-lower-and-float-upper-bound",
            ),
            pytest.param(
                "{0 TO 10.5}",
                id="exclusive-integer-lower-and-float-upper-bound",
            ),
            pytest.param(
                "{0 TO 10.5]",
                id="exclusive-inclusive-integer-lower-and-float-upper-bound",
            ),
            pytest.param(
                "[0 TO 10.5}",
                id="inclusive-exclusive-integer-lower-and-float-upper-bound",
            ),
            pytest.param(
                "[-10.5 TO 10]",
                id="float-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "{-10.5 TO 10}",
                id="exclusive-float-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "{-10.5 TO 10]",
                id="exclusive-inclusive-float-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "[-10.5 TO 10}",
                id="inclusive-exclusive-float-lower-and-integer-upper-bound",
            ),
        ),
    )
    def test_create_rejects_mixed_integer_and_float_range_boundaries(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(f'The expression "{range_expression}" is invalid!'),
        ):
            LuceneFilter.create(range_query(range_expression))

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[1 TO bar]",
                id="integer-lower-and-string-upper-bound",
            ),
            pytest.param(
                "{1 TO bar}",
                id="exclusive-integer-lower-and-string-upper-bound",
            ),
            pytest.param(
                "{1 TO bar]",
                id="exclusive-inclusive-integer-lower-and-string-upper-bound",
            ),
            pytest.param(
                "[1 TO bar}",
                id="inclusive-exclusive-integer-lower-and-string-upper-bound",
            ),
            pytest.param(
                "[foo TO 10]",
                id="string-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "{foo TO 10}",
                id="exclusive-string-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "{foo TO 10]",
                id="exclusive-inclusive-string-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "[foo TO 10}",
                id="inclusive-exclusive-string-lower-and-integer-upper-bound",
            ),
            pytest.param(
                "[1.5 TO bar]",
                id="float-lower-and-string-upper-bound",
            ),
            pytest.param(
                "{1.5 TO bar}",
                id="exclusive-float-lower-and-string-upper-bound",
            ),
            pytest.param(
                "{1.5 TO bar]",
                id="exclusive-inclusive-float-lower-and-string-upper-bound",
            ),
            pytest.param(
                "[1.5 TO bar}",
                id="inclusive-exclusive-float-lower-and-string-upper-bound",
            ),
            pytest.param(
                "[foo TO 10.5]",
                id="string-lower-and-float-upper-bound",
            ),
            pytest.param(
                "{foo TO 10.5}",
                id="exclusive-string-lower-and-float-upper-bound",
            ),
            pytest.param(
                "{foo TO 10.5]",
                id="exclusive-inclusive-string-lower-and-float-upper-bound",
            ),
            pytest.param(
                "[foo TO 10.5}",
                id="inclusive-exclusive-string-lower-and-float-upper-bound",
            ),
        ),
    )
    def test_create_rejects_mixed_numeric_and_string_range_boundaries(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(f'The expression "{range_expression}" is invalid!'),
        ):
            LuceneFilter.create(range_query(range_expression))

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[* TO 10]",
                id="open-lower-bound",
            ),
            pytest.param(
                "{* TO 10}",
                id="exclusive-open-lower-bound",
            ),
            pytest.param(
                "[1 TO *]",
                id="open-upper-bound",
            ),
            pytest.param(
                "{1 TO *}",
                id="exclusive-open-upper-bound",
            ),
            pytest.param(
                "[* TO *]",
                id="fully-open-range",
            ),
            pytest.param(
                "{* TO *}",
                id="exclusive-fully-open-range",
            ),
            pytest.param(
                "[* TO foo]",
                id="open-lower-string-upper-bound",
            ),
            pytest.param(
                "[foo TO *]",
                id="string-lower-open-upper-bound",
            ),
        ),
    )
    def test_create_rejects_open_range(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(f'The expression "{range_expression}" is invalid!'),
        ):
            LuceneFilter.create(range_query(range_expression))

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[nan TO 10]",
                id="nan-lower-bound",
            ),
            pytest.param(
                "{nan TO 10}",
                id="exclusive-nan-lower-bound",
            ),
            pytest.param(
                "[0 TO nan]",
                id="nan-upper-bound",
            ),
            pytest.param(
                "{0 TO nan}",
                id="exclusive-nan-upper-bound",
            ),
            pytest.param(
                "[-inf TO 10]",
                id="negative-infinity-lower-bound",
            ),
            pytest.param(
                "{-inf TO 10}",
                id="exclusive-negative-infinity-lower-bound",
            ),
            pytest.param(
                "[0 TO inf]",
                id="positive-infinity-upper-bound",
            ),
            pytest.param(
                "{0 TO inf}",
                id="exclusive-positive-infinity-upper-bound",
            ),
        ),
    )
    def test_create_rejects_non_finite_range_boundaries(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(f'The expression "{range_expression}" is invalid!'),
        ):
            LuceneFilter.create(range_query(range_expression))

    def test_created_range_filter_prefers_integer_range_over_string_range(
        self,
        range_query,
    ):
        lucene_filter = LuceneFilter.create(range_query("[1 TO 10]"))

        assert lucene_filter.matches({"key": 2})
        assert lucene_filter.matches({"key": 10})
        assert not lucene_filter.matches({"key": "2"})

    def test_created_range_filter_prefers_float_range_over_string_range(
        self,
        range_query,
    ):
        lucene_filter = LuceneFilter.create(range_query("[1.5 TO 10.5]"))

        assert lucene_filter.matches({"key": 2.0})
        assert lucene_filter.matches({"key": 10.5})
        assert not lucene_filter.matches({"key": "2.0"})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z]",
                (
                    "2024-01-01T00:00:00Z",
                    "2024-06-15T12:30:00Z",
                    "2024-12-31T23:59:59Z",
                ),
                (
                    "2023-12-31T23:59:59Z",
                    "2025-01-01T00:00:00Z",
                ),
                id="iso-8601-utc-timestamp-range",
            ),
            pytest.param(
                "[2024-01-01T00:00:00.000Z TO 2024-01-01T00:00:00.999Z]",
                (
                    "2024-01-01T00:00:00.000Z",
                    "2024-01-01T00:00:00.500Z",
                    "2024-01-01T00:00:00.999Z",
                ),
                (
                    "2023-12-31T23:59:59.999Z",
                    "2024-01-01T00:00:01.000Z",
                ),
                id="iso-8601-millisecond-timestamp-range",
            ),
            pytest.param(
                '["2024-01-01T00:00:00+01:00" TO "2024-12-31T23:59:59+01:00"]',
                (
                    "2024-01-01T00:00:00+01:00",
                    "2024-06-15T12:30:00+01:00",
                    "2024-12-31T23:59:59+01:00",
                ),
                (
                    "2023-12-31T23:59:59+01:00",
                    "2025-01-01T00:00:00+01:00",
                ),
                id="quoted-iso-8601-offset-timestamp-range",
            ),
        ),
    )
    def test_created_string_range_filter_matches_iso_8601_timestamps_lexicographically(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        ("range_expression", "matching_values", "non_matching_values"),
        (
            pytest.param(
                "[2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z]",
                (
                    "2024-01-01T00:00:00Z",
                    "2024-06-15T12:30:00Z",
                    "2024-12-31T23:59:59Z",
                ),
                (
                    "2023-12-31T23:59:59Z",
                    "2025-01-01T00:00:00Z",
                ),
                id="iso-8601-inclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "{2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z}",
                ("2024-06-15T12:30:00Z",),
                (
                    "2024-01-01T00:00:00Z",
                    "2024-12-31T23:59:59Z",
                ),
                id="iso-8601-exclusive-lower-exclusive-upper",
            ),
            pytest.param(
                "{2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z]",
                (
                    "2024-06-15T12:30:00Z",
                    "2024-12-31T23:59:59Z",
                ),
                (
                    "2024-01-01T00:00:00Z",
                    "2025-01-01T00:00:00Z",
                ),
                id="iso-8601-exclusive-lower-inclusive-upper",
            ),
            pytest.param(
                "[2024-01-01T00:00:00Z TO 2024-12-31T23:59:59Z}",
                (
                    "2024-01-01T00:00:00Z",
                    "2024-06-15T12:30:00Z",
                ),
                (
                    "2023-12-31T23:59:59Z",
                    "2024-12-31T23:59:59Z",
                ),
                id="iso-8601-inclusive-lower-exclusive-upper",
            ),
            pytest.param(
                '["2024-01-01T00:00:00+01:00" TO "2024-12-31T23:59:59+01:00"]',
                (
                    "2024-01-01T00:00:00+01:00",
                    "2024-06-15T12:30:00+01:00",
                    "2024-12-31T23:59:59+01:00",
                ),
                (
                    "2023-12-31T23:59:59+01:00",
                    "2025-01-01T00:00:00+01:00",
                ),
                id="quoted-iso-8601-offset-inclusive-lower-inclusive-upper",
            ),
            pytest.param(
                '{"2024-01-01T00:00:00+01:00" TO "2024-12-31T23:59:59+01:00"}',
                ("2024-06-15T12:30:00+01:00",),
                (
                    "2024-01-01T00:00:00+01:00",
                    "2024-12-31T23:59:59+01:00",
                ),
                id="quoted-iso-8601-offset-exclusive-lower-exclusive-upper",
            ),
        ),
    )
    def test_created_string_range_filter_respects_iso_8601_timestamp_boundary_inclusiveness(
        self,
        range_query,
        range_expression,
        matching_values,
        non_matching_values,
    ):
        lucene_filter = LuceneFilter.create(range_query(range_expression))

        for value in matching_values:
            assert lucene_filter.matches({"key": value})

        for value in non_matching_values:
            assert not lucene_filter.matches({"key": value})

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[2024-12-31T23:59:59Z TO 2024-01-01T00:00:00Z]",
                id="reversed-inclusive-iso-8601-timestamp-range",
            ),
            pytest.param(
                "{2024-12-31T23:59:59Z TO 2024-01-01T00:00:00Z}",
                id="reversed-exclusive-iso-8601-timestamp-range",
            ),
            pytest.param(
                "{2024-12-31T23:59:59Z TO 2024-01-01T00:00:00Z]",
                id="reversed-exclusive-inclusive-iso-8601-timestamp-range",
            ),
            pytest.param(
                "[2024-12-31T23:59:59Z TO 2024-01-01T00:00:00Z}",
                id="reversed-inclusive-exclusive-iso-8601-timestamp-range",
            ),
            pytest.param(
                '["2024-12-31T23:59:59+01:00" TO "2024-01-01T00:00:00+01:00"]',
                id="reversed-quoted-iso-8601-offset-timestamp-range",
            ),
        ),
    )
    def test_create_rejects_reversed_iso_8601_timestamp_range(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match=re.escape(
                "The lower range boundary must not exceed "
                f'the upper range boundary: "{range_expression}"'
            ),
        ):
            LuceneFilter.create(range_query(range_expression))

    @pytest.mark.parametrize(
        "range_expression",
        (
            pytest.param(
                "[2024-01-01T00:00:00+01:00 TO 2024-12-31T23:59:59+01:00]",
                id="unquoted-iso-8601-offset-inclusive-range",
            ),
            pytest.param(
                "{2024-01-01T00:00:00+01:00 TO 2024-12-31T23:59:59+01:00}",
                id="unquoted-iso-8601-offset-exclusive-range",
            ),
            pytest.param(
                "{2024-01-01T00:00:00+01:00 TO 2024-12-31T23:59:59+01:00]",
                id="unquoted-iso-8601-offset-exclusive-inclusive-range",
            ),
            pytest.param(
                "[2024-01-01T00:00:00+01:00 TO 2024-12-31T23:59:59+01:00}",
                id="unquoted-iso-8601-offset-inclusive-exclusive-range",
            ),
        ),
    )
    def test_create_rejects_unquoted_iso_8601_offset_timestamp_range(
        self,
        range_query,
        range_expression,
    ):
        with pytest.raises(
            LuceneFilterError,
            match="expression not escaped correctly",
        ):
            LuceneFilter.create(range_query(range_expression))
