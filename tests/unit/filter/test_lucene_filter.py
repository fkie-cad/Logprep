# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
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

    def test_creates_lucene_compliance_filter_parentheses_or_one_regex(self):
        lucene_filter = LuceneFilter.create('regex_key_one: (/.*value_one.*/ OR "/.*value_two.*/")')

        assert lucene_filter == Or(
            RegExFilterExpression(["regex_key_one"], ".*value_one.*"),
            StringFilterExpression(["regex_key_one"], "/.*value_two.*/"),
        )
