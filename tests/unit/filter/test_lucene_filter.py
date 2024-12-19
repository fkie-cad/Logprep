# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
import re

import pytest
from pytest import raises

from logprep.filter.expression.filter_expression import (
    And,
    Always,
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
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("One single escaped quotation (1->2)", '\\"', '\\\\"'),
        ("One double escaped quotation (2->4)", '\\\\"', '\\\\\\\\"'),
        ("One triple escaped quotation (3->6)", '\\\\\\"', '\\\\\\\\\\\\"'),
        ("Escaped not last", '\\"foo\\"', '\\"foo\\\\"'),
        ("Two quotations", '""', '""'),
        ("Three single escaped quotation", '\\"\\"\\"', '\\"\\"\\\\"'),
        ("One double escaped quotation at beginning", '\\\\"\\"', '\\\\"\\\\"'),
        ("Quotation ends with AND", '\\" AND', '\\\\" AND'),
        ("Quotation ends with OR", '\\" OR', '\\\\" OR'),
        ("Quotation ends with NOT", '\\" NOT', '\\\\" NOT'),
        ("Quotation doesn't end with AND/OR/NOT/$", '\\" foo', '\\" foo'),
        ("Quotation with parenthesis ends with AND", '\\") AND', '\\\\") AND'),
        ("Quotation with parenthesis ends with OR", '\\") OR', '\\\\") OR'),
        ("Quotation with parenthesis ends with NOT", '\\") NOT', '\\\\") NOT'),
        ("Quotation with parenthesis doesn't end with AND/OR/NOT/$", '\\") foo', '\\") foo'),
        ("Word between quotation and AND", '\\"foo AND', '\\"foo AND'),
        ("Word between quotation and OR", '\\"foo OR', '\\"foo OR'),
        ("Word between quotation and NOT", '\\"foo NOT', '\\"foo NOT'),
        ("One escape character", "\\", "\\"),
        ("Two escape characters", "\\\\", "\\\\"),
    ]

    @pytest.mark.parametrize(
        "testcase, input_string, escaped_string",
        escape_ends_of_expressions_test_cases,
    )
    def test_escape_ends_of_expressions(self, testcase, input_string, escaped_string):
        result = LuceneFilter._escape_ends_of_expressions(input_string)
        assert result == escaped_string, testcase

    unescape_ends_of_expressions_test_cases = [
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("Two quotations", '""', '""'),
        ("Unescape (6->3->1)", f"{esc(6)}", f"{esc(1)}"),
        ("Don't unescape if quotation (1->1)", '\\"', '\\"'),
        ("Unescape (10->5->2)", f"{esc(10)}", f"{esc(2)}"),
        ("Four escaped quotations (14->7->3)", f"{esc(14)}", f"{esc(3)}"),
        ("Escaped not last", f'\\"foo{esc(6)}', '\\"foo\\'),
        ("Two single escaped quotation", f'\\"\\"{esc(6)}', '\\"\\"\\'),
        ("One double escaped quotation at beginning", f'{esc(2)}"{esc(6)}', f'{esc(2)}"{esc(1)}'),
    ]

    @pytest.mark.parametrize(
        "testcase, input_string, unescaped_string",
        unescape_ends_of_expressions_test_cases,
    )
    def test_remove_escaping_from_end_of_expression(self, testcase, input_string, unescaped_string):
        result = LuceneTransformer._remove_escaping_from_end_of_expression(input_string)
        assert result == unescaped_string, testcase

    uneven_double_quotes_escaping_test_cases = [
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("Two quotations", '""', '""'),
        ("One single escaped quotation (1->3)", '\\"', '\\\\\\"'),
        ("One double escaped quotation (2->5)", '\\\\"', '\\\\\\\\\\"'),
        ("One triple escaped quotation (3->7)", '\\\\\\"', '\\\\\\\\\\\\\\"'),
        ("Escaped not last (1->3)", '\\"foo\\"', '\\\\\\"foo\\\\\\"'),
        ("Three single escaped quotation (1->3)", '\\"\\"\\"', '\\\\\\"\\\\\\"\\\\\\"'),
        ("One double escaped quotation at beginning", '\\\\"\\"', '\\\\\\\\\\"\\\\\\"'),
        ("Quotation ends with AND", '\\" AND', '\\\\\\" AND'),
        ("Quotation ends with OR", '\\" OR', '\\\\\\" OR'),
        ("Quotation ends with NOT", '\\" NOT', '\\\\\\" NOT'),
        ("Quotation doesn't end with AND/OR/NOT/$", '\\" foo', '\\\\\\" foo'),
        ("Quotation with parenthesis ends with AND", '\\") AND', '\\\\\\") AND'),
        ("Quotation with parenthesis ends with OR", '\\") OR', '\\\\\\") OR'),
        ("Quotation with parenthesis ends with NOT", '\\") NOT', '\\\\\\") NOT'),
        ("Quotation with parenthesis doesn't end with keyword", '\\") foo', '\\\\\\") foo'),
        ("Word between quotation and AND", '\\"foo AND', '\\\\\\"foo AND'),
        ("Word between quotation and OR", '\\"foo OR', '\\\\\\"foo OR'),
        ("Word between quotation and NOT", '\\"foo NOT', '\\\\\\"foo NOT'),
        ("One escape character", "\\", "\\"),
        ("Two escape characters", "\\\\", "\\\\"),
    ]

    @pytest.mark.parametrize(
        "testcase, input_string, escaped_string",
        uneven_double_quotes_escaping_test_cases,
    )
    def test_make_uneven_double_quotes_escaping(self, testcase, input_string, escaped_string):
        result = LuceneFilter._make_uneven_double_quotes_escaping(input_string)
        assert result == escaped_string, testcase

    @pytest.mark.parametrize(
        "testcase, input_string, escaped_string",
        uneven_double_quotes_escaping_test_cases,
    )
    def test_remove_uneven_double_quotes_escaping(self, testcase, input_string, escaped_string):
        result = LuceneTransformer._remove_uneven_double_quotes_escaping(escaped_string)
        assert result == input_string, testcase

    add_escaping_test_cases = [
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("One single escaped quotation (1->3->6)", '\\"', f'{esc(6)}"'),
        ("One double escaped quotation (2->5->10)", '\\\\"', f'{esc(10)}"'),
        ("One triple escaped quotation (3->7->14)", '\\\\\\"', f'{esc(14)}"'),
        ("Escaped not last", '\\"foo\\"', f'{esc(3)}"foo{esc(6)}"'),
        ("Two quotations", '""', '""'),
        ("Three single escaped quotation", '\\"\\"\\"', f'{esc(3)}"{esc(3)}"{esc(6)}"'),
        ("One double escaped quotation at beginning", '\\\\"\\"', f'{esc(5)}"{esc(6)}"'),
        ("Quotation ends with AND", '\\" AND', f'{esc(6)}" AND'),
        ("Quotation ends with OR", '\\" OR', f'{esc(6)}" OR'),
        ("Quotation ends with NOT", '\\" NOT', f'{esc(6)}" NOT'),
        ("Quotation doesn't end with AND/OR/NOT/$", '\\" foo', f'{esc(3)}" foo'),
        ("Quotation with parenthesis ends with AND", '\\") AND', f'{esc(6)}") AND'),
        ("Quotation with parenthesis ends with OR", '\\") OR', f'{esc(6)}") OR'),
        ("Quotation with parenthesis ends with NOT", '\\") NOT', f'{esc(6)}") NOT'),
        ("Quotation with parenthesis doesn't end with AND/OR/NOT/$", '\\") foo', f'{esc(3)}") foo'),
        ("Word between quotation and AND", '\\"foo AND', f'{esc(3)}"foo AND'),
        ("Word between quotation and OR", '\\"foo OR', f'{esc(3)}"foo OR'),
        ("Word between quotation and NOT", '\\"foo NOT', f'{esc(3)}"foo NOT'),
        ("One escape character", "\\", "\\"),
        ("Two escape characters", "\\\\", "\\\\"),
    ]

    @pytest.mark.parametrize(
        "testcase, input_string, escaped_string",
        add_escaping_test_cases,
    )
    def test_add_lucene_escaping(self, testcase, input_string, escaped_string):
        result = LuceneFilter._add_lucene_escaping(input_string)
        assert result == escaped_string, testcase

    remove_one_escaping_from_quotes = [
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("Two quotations", '""', '""'),
        ("One escape at the end (1->1)", "\\", "\\"),
        ("Two escapes at the end (2->2)", "\\\\", "\\\\"),
        ("Three escapes at the end (3->2)", "\\\\\\", "\\\\\\"),
        ("One single escaped quotation (1->0)", '\\"', '"'),
        ("One double escaped quotation (2->1)", '\\\\"', '\\"'),
        ("One triple escaped quotation (3->2)", '\\\\\\"', '\\\\"'),
        ("Escaped not last", '\\"foo\\"', '"foo"'),
        ("Three single escaped quotation", '\\"\\"\\"', '"""'),
        ("Quotation ends with AND", '\\" AND', '" AND'),
        ("Quotation ends with OR", '\\" OR', '" OR'),
        ("Quotation ends with NOT", '\\" NOT', '" NOT'),
    ]

    @pytest.mark.parametrize(
        "testcase, input_string, escaped_string",
        remove_one_escaping_from_quotes,
    )
    def test_remove_one_escaping_from_quotes(self, testcase, input_string, escaped_string):
        result = LuceneTransformer._remove_one_escaping_from_quotes(input_string)
        assert result == escaped_string, testcase

    remove_escaping_test_cases = [
        (case, expected, test_input) for case, test_input, expected in add_escaping_test_cases
    ]

    remove_escaping_test_cases_end_escaping = [
        ("One quote character", '"', '"'),
        ("One escape character", esc(1), esc(0)),
        ("Six escape characters", esc(6), esc(1)),
        ("Ten escape characters", esc(10), esc(2)),
        ("One escape character with quotation after", f'{esc(1)}"', f'{esc(0)}"'),
        ("Six escape characters with quotation after", f'{esc(6)}"', f'{esc(2)}"'),
        ("Ten escape characters with quotation after", f'{esc(10)}"', f'{esc(4)}"'),
        ("Twelve escape characters with quotation after", f'{esc(12)}"', f'{esc(5)}"'),
        ("One escape character with quotation before", f'"{esc(1)}', f'"{esc(0)}'),
        ("Two escape characters with quotation before", f'"{esc(6)}', f'"{esc(1)}'),
        ("Four escape characters with quotation before", f'"{esc(10)}', f'"{esc(2)}'),
        ("One escape character with quotation not last", f'{esc(1)}"x', f'{esc(0)}"x'),
        ("Two escape characters with quotation ot last", f'{esc(6)}"x', f'{esc(2)}"x'),
        ("Four escape characters with quotation ot last", f'{esc(10)}"x', f'{esc(4)}"x'),
    ]

    @pytest.mark.parametrize(
        "testcase, escaped_string, unescaped_string",
        remove_escaping_test_cases_end_escaping,
    )
    def test_remove_lucene_escaping(self, testcase, escaped_string, unescaped_string):
        result = LuceneTransformer._remove_lucene_escaping(escaped_string)
        assert result == unescaped_string, testcase

    create_filter_success_test_cases = [
        ("Empty string", "", ""),
        ("No escaping", "\\", "\\"),
        ("Escaped words", "\\foo \\bar", "\\foo \\bar"),
        ("One single escaped quotation", '\\"', '"'),
        ("One triple escaped quotation", '\\\\\\"', '\\\\"'),
        ("Path", "\\foo\\bar\\", "\\foo\\bar\\"),
        ("Escaped path", "\\\\foo\\\\bar\\\\", "\\\\foo\\\\bar\\\\"),
        ("One double escaped quotation at end", '\\"\\', '"\\'),
    ]

    @pytest.mark.parametrize("testcase, input_str, cleaned_str", create_filter_success_test_cases)
    def test_create_filter_success(self, testcase, input_str, cleaned_str):
        test_filter = LuceneFilter.create(f'foo: "{input_str}"')
        assert test_filter == StringFilterExpression(["foo"], cleaned_str), testcase

    create_filter_fail_test_cases = [
        (
            "One not escaped quotation",
            '"',
            "Illegal character '\"' at position 7 in 'foo: \"\"\"' - "
            + "expression not escaped correctly",
        ),
        ("Two not escaped quotation", '""', 'The expression "foo: """"" is invalid!'),
        (
            "Quotation doesn't end with AND/OR/NOT/$",
            '" bar',
            'The expression "foo: "" bar"" is invalid!',
        ),
    ]

    @pytest.mark.parametrize("testcase, input_str, message", create_filter_fail_test_cases)
    def test_create_filter_error(self, testcase, input_str, message):
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

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], "\/.*value.*")

    def test_new_lucene_compliance_single_escape(self):
        lucene_filter = LuceneFilter.create("regex_key_one:/\/.*value.*/")

        assert lucene_filter == RegExFilterExpression(["regex_key_one"], "\/.*value.*")
