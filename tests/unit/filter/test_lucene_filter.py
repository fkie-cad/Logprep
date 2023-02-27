# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
import pytest
from pytest import raises

from logprep.filter.lucene_filter import LuceneFilter, LuceneFilterError, LuceneTransformer
from logprep.filter.expression.filter_expression import (
    StringFilterExpression,
    RegExFilterExpression,
    Or,
    And,
    Null,
    Always,
)


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

    add_escaping_test_cases = [
        ("Empty string", "", ""),
        ("No escaping", "foo bar baz", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz", "\\foo \\bar \\baz"),
        ("One quotation", '"', '"'),
        ("One single escaped quotation", '"', '"'),
        ("One double escaped quotation", '\\"', '\\\\"'),
        ("One quadruple escaped quotation", '\\\\"', '\\\\\\\\"'),
        ("Escaped not last", '\\"foo\\"', '\\"foo\\\\"'),
        ("Two quotations", '""', '""'),
        ("Three double escaped quotation", '\\"\\"\\"', '\\"\\"\\\\"'),
        ("One double escaped quotation at beginning", '\\"\\"', '\\"\\\\"'),
        ("One quadruple escaped quotation at beginning", '\\\\"\\"', '\\\\\\"\\\\"'),
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
    ]

    add_escaping_test_cases_end_escaping = [
        ("One escape character", "\\", "\\"),
        ("Two escape characters", "\\\\", "\\\\"),
    ]

    @pytest.mark.parametrize(
        "testcase, query_string, escaped_string",
        add_escaping_test_cases + add_escaping_test_cases_end_escaping,
    )
    def test_add_lucene_escaping(self, testcase, query_string, escaped_string):
        result = LuceneFilter._add_lucene_escaping(query_string)

        assert result == escaped_string, testcase

    remove_escaping_test_cases = [
        (case, expected, test_input) for case, test_input, expected in add_escaping_test_cases
    ]

    remove_escaping_test_cases_end_escaping = [
        ("One escape character", "\\", ""),
        ("Two escape characters", "\\\\", "\\"),
        ("Four escape characters", "\\\\\\\\", "\\\\"),
    ]

    @pytest.mark.parametrize(
        "testcase, escaped_string, unescaped_string",
        remove_escaping_test_cases + remove_escaping_test_cases_end_escaping,
    )
    def test_remove_lucene_escaping(self, testcase, escaped_string, unescaped_string):
        result = LuceneTransformer._remove_lucene_escaping(escaped_string)

        assert result == unescaped_string, testcase

    create_filter_test_cases = [
        ("Empty string", ""),
        ("No escaping", "foo bar baz"),
        ("Escaped words", "\\foo \\bar \\baz"),
        ("One double escaped quotation", '\\"'),
        ("One quadruple escaped quotation", '\\\\"'),
        ("Path", "\\foo\\bar\\baz\\"),
        ("Escaped path", "\\\\foo\\\\bar\\\\baz\\\\"),
        ("Three double escaped quotation", '\\"\\"\\"'),
        ("One double escaped quotation at beginning", '\\"\\"'),
        ("One quadruple escaped quotation at beginning", '\\\\"\\"'),
        ("One quadruple escaped quotation at end", '\\"\\\\"'),
    ]

    @pytest.mark.parametrize("testcase, input_string", create_filter_test_cases)
    def test_creates_expected_filter_from_windows_path_query(self, testcase, input_string):
        test_filter = LuceneFilter.create(f'foo: "{input_string}"')
        assert test_filter == StringFilterExpression(["foo"], input_string), testcase
