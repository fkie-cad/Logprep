from pytest import raises

from logprep.filter.lucene_filter import LuceneFilter, LuceneFilterError
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
        filter = LuceneFilter.create('key: "value"')

        assert filter == StringFilterExpression(["key"], "value")

    def test_creates_expected_filter_from_simple_expression(self):
        filter = LuceneFilter.create('(title:"foo bar" AND body:"quick fox") OR title:fox')

        assert filter == Or(
            And(
                StringFilterExpression(["title"], "foo bar"),
                StringFilterExpression(["body"], "quick fox"),
            ),
            StringFilterExpression(["title"], "fox"),
        )

    def test_created_filter_does_not_match_document_without_requested_key(self):
        filter = LuceneFilter.create('key: "value"')

        assert not filter.matches({"not the key": "not the value"})

    def test_created_filter_does_not_match_document_without_wrong_value(self):
        filter = LuceneFilter.create('key: "value"')

        assert not filter.matches({"key": "not the value"})

    def test_created_filter_matches_document_with_correct_value(self):
        filter = LuceneFilter.create('key: "value"')

        assert filter.matches({"key": "value"})

    def test_created_filter_matches_document_with_parenthesis(self):
        filter = LuceneFilter.create('(key: "value")')

        assert filter.matches({"key": "value"})

    def test_created_and_filter_matches_or_value(self):
        filter = LuceneFilter.create('key: ("value" OR "value2")')

        assert not filter.matches({})
        assert not filter.matches({"key": "wrong value"})

        assert filter.matches({"key": "value"})
        assert filter.matches({"key": "value2"})

    def test_created_and_filter_matches_only_document_with_both_correct_value(self):
        filter = LuceneFilter.create('key: "value" AND key2: "value2"')

        assert not filter.matches({})
        assert not filter.matches({"key": "value"})
        assert not filter.matches({"key2": "value2"})
        assert not filter.matches({"key": "wrong value", "key2": "value2"})
        assert not filter.matches({"key": "value", "key2": "wrong value"})
        assert not filter.matches({"key": "wrong value", "key2": "wrong value"})

        assert filter.matches({"key": "value", "key2": "value2"})

    def test_created_or_filter_matches_any_document_with_one_correct_value(self):
        filter = LuceneFilter.create('key: "value" OR key2: "value2"')

        assert not filter.matches({})
        assert not filter.matches({"key": "wrong value", "key2": "wrong value"})

        assert filter.matches({"key": "value"})
        assert filter.matches({"key2": "value2"})
        assert filter.matches({"key": "wrong value", "key2": "value2"})
        assert filter.matches({"key": "value", "key2": "wrong value"})
        assert filter.matches({"key": "value", "key2": "value2"})

    def test_creates_expected_filter_from_query_tagged_as_regex(self):
        filter = LuceneFilter.create('key: "value"', special_fields={"regex_fields": ["key"]})

        assert filter == RegExFilterExpression(["key"], "value")

    def test_creates_expected_filter_from_query_tagged_as_regex_with_field_group(self):
        filter = LuceneFilter.create(
            'key: ("value" OR "value2")', special_fields={"regex_fields": ["key"]}
        )

        assert filter == Or(
            RegExFilterExpression(["key"], "value"), RegExFilterExpression(["key"], "value2")
        )

    def test_creates_expected_filter_from_regex_query(self):
        filter = LuceneFilter.create('key: ".*value.*"', special_fields={"regex_fields": ["key"]})

        assert filter == RegExFilterExpression(["key"], ".*value.*")

    def test_creates_expected_filter_from_regex_query_with_dot_partially(self):
        filter = LuceneFilter.create('event.key: "value"', special_fields={"regex_fields": ["key"]})

        assert filter == StringFilterExpression(["event", "key"], "value")

    def test_creates_expected_filter_from_regex_query_with_dot(self):
        filter = LuceneFilter.create(
            'event.key: ".*value.*"', special_fields={"regex_fields": ["event.key"]}
        )

        assert filter == RegExFilterExpression(["event", "key"], ".*value.*")

    def test_creates_string_filter_without_matching_regex_key(self):
        filter = LuceneFilter.create(
            'key: ".*value.*"', special_fields={"regex_fields": ["i_do_not_match"]}
        )

        assert filter == StringFilterExpression(["key"], ".*value.*")

    def test_creates_string_filter_with_two_matching_regex_keys_of_two(self):
        filter = LuceneFilter.create(
            'regex_key_one: ".*value.*" AND regex_key_two: ".*value.*"',
            special_fields={"regex_fields": ["regex_key_one", "regex_key_two"]},
        )

        assert filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            RegExFilterExpression(["regex_key_two"], ".*value.*"),
        )

    def test_creates_string_filter_with_one_matching_and_one_missmatching_regex_key_of_two(self):
        filter = LuceneFilter.create(
            'regex_key_one: ".*value.*" AND key_two: "value"',
            special_fields={"regex_fields": ["regex_key_one", "i_dont_exist"]},
        )

        assert filter == And(
            RegExFilterExpression(["regex_key_one"], ".*value.*"),
            StringFilterExpression(["key_two"], "value"),
        )

    def test_creates_string_filter_with_one_matching_regex_key_of_two(self):
        filter = LuceneFilter.create(
            'regex_key: ".*value.*" AND string_key: "value"',
            special_fields={"regex_fields": ["regex_key"]},
        )

        assert filter == And(
            RegExFilterExpression(["regex_key"], ".*value.*"),
            StringFilterExpression(["string_key"], "value"),
        )

    def test_creates_string_filter_with_pipe_regex(self):
        filter = LuceneFilter.create('regex_key|re: ".*value.*" AND string_key: "value"')

        assert filter == And(
            RegExFilterExpression(["regex_key"], ".*value.*"),
            StringFilterExpression(["string_key"], "value"),
        )

    def test_does_not_create_null_filter_with_string(self):
        filter = LuceneFilter.create('null_key: "null"')

        assert filter == StringFilterExpression(["null_key"], "null")

    def test_creates_null_filter(self):
        filter = LuceneFilter.create("null_key: null")

        assert filter == Null(["null_key"])

    def test_creates_null_filter_dotted(self):
        filter = LuceneFilter.create("something.null_key: null")

        assert filter == Null(["something", "null_key"])

    def test_creates_filter_escaped(self):
        filter = LuceneFilter.create('a\\ key\\(: "value"')

        assert filter == StringFilterExpression(["a key("], "value")

    def test_creates_filter_escaped_with_regex_tag(self):
        filter = LuceneFilter.create('a\\ key\\(|re: "value"')

        assert filter == RegExFilterExpression(["a key("], "value")

    def test_creates_filter_escaped_with_dotted_regex_tag(self):
        filter = LuceneFilter.create('key.a\\ subkey\\(|re: "value"')

        assert filter == RegExFilterExpression(["key", "a subkey("], "value")

    def test_creates_filter_not_escaped_raises_exception(self):
        with raises(LuceneFilterError):
            LuceneFilter.create('a key(: "value"')

    def test_creates_filter_match_all(self):
        filter = LuceneFilter.create("*")

        assert filter == Always(True)
