# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
# pylint: disable=redefined-builtin
# pylint: disable=protected-access
from random import sample
from string import ascii_letters, digits

from pytest import raises

from logprep.filter.expression.filter_expression import (
    FilterExpression,
    KeyDoesNotExistError,
    StringFilterExpression,
    IntegerFilterExpression,
    And,
    Or,
    Not,
    RegExFilterExpression,
    IntegerRangeFilterExpression,
    FloatRangeFilterExpression,
    FloatFilterExpression,
    Always,
    WildcardStringFilterExpression,
    SigmaFilterExpression,
    Exists,
)


class TestFilterExpression:
    def test_get_value_fails_for_missing_key(self):
        with raises(KeyDoesNotExistError):
            FilterExpression._get_value(["some", "key"], {})

    def test_get_value_fails_empty_key(self):
        with raises(KeyDoesNotExistError):
            FilterExpression._get_value([], {"some": "value"})

    def test_get_value_returns_expected_value(self):
        document = {"one": {"two": "value"}, "ten": {"eleven": "another value"}}

        assert FilterExpression._get_value(["one", "two"], document) == "value"


class TestAlways:
    def setup_class(self):
        self.documents = [{}, {"key": "value"}, {"integer": 42}]

    def test_string_representation(self):
        assert str(Always(True)) == "TRUE"
        assert str(Always(False)) == "FALSE"

    def test_different_objects_with_same_payload_are_equal(self):
        filter1 = Always(False)
        filter2 = Always(False)

        assert filter1 == filter2

    def test_false_is_false_regardless_of_document(self):
        for document in self.documents:
            assert not Always(False).matches(document)

    def test_true_is_true_regardless_of_document(self):
        for document in self.documents:
            assert Always(True).matches(document)


class TestNot:
    def test_string_representation(self):
        assert str(Not(Always(True))) == "NOT(TRUE)"

    def test_different_objects_with_same_payload_are_equal(self):
        not_filter1 = Not(Always(True))
        not_filter2 = Not(Always(True))

        assert not_filter1 == not_filter2

    def test_a_true_becomes_false(self):
        not_filter = Not(Always(True))
        assert not not_filter.matches({})

    def test_a_false_becomes_true(self):
        not_filter = Not(Always(False))
        assert not_filter.matches({})


class TestAnd:
    def test_string_representation(self):
        assert str(And(Always(True))) == "AND(TRUE)"

    def test_different_objects_with_same_payload_are_equal(self):
        and_filter1 = And(Always(False))
        and_filter2 = And(Always(False))

        assert and_filter1 == and_filter2

    def test_a_single_false_is_false(self):
        and_filter = And(Always(False))
        assert not and_filter.matches({})

    def test_a_single_true_is_true(self):
        and_filter = And(Always(True))
        assert and_filter.matches({})

    def test_matches_two_bit_truth_table(self):
        for left in [True, False]:
            for right in [True, False]:
                and_filter = And(Always(left), Always(right))
                if left and right:
                    assert and_filter.matches({})
                else:
                    assert not and_filter.matches({})

    def test_matches_three_bit_truth_table(self):
        for left in [True, False]:
            for center in [True, False]:
                for right in [True, False]:
                    and_filter = And(Always(left), Always(center), Always(right))
                    if left and center and right:
                        assert and_filter.matches({})
                    else:
                        assert not and_filter.matches({})


class TestOr:
    def test_string_representation(self):
        assert str(Or(Always(True))) == "OR(TRUE)"

    def test_different_objects_with_same_payload_are_equal(self):
        or_filter1 = Or(Always(False))
        or_filter2 = Or(Always(False))

        assert or_filter1 == or_filter2

    def test_a_single_false_is_false(self):
        or_filter = Or(Always(False))
        assert not or_filter.matches({})

    def test_a_single_true_is_true(self):
        or_filter = Or(Always(True))
        assert or_filter.matches({})

    def test_matches_two_bit_truth_table(self):
        for left in [True, False]:
            for right in [True, False]:
                or_filter = Or(Always(left), Always(right))
                if (not left) and (not right):
                    assert not or_filter.matches({})
                else:
                    assert or_filter.matches({})

    def test_matches_three_bit_truth_table(self):
        for left in [True, False]:
            for center in [True, False]:
                for right in [True, False]:
                    or_filter = Or(Always(left), Always(center), Always(right))
                    if (not left) and (not center) and (not right):
                        assert not or_filter.matches({})
                    else:
                        assert or_filter.matches({})


class ValueBasedFilterExpressionTest:
    # pylint: disable=no-member
    def test_does_not_match_if_key_is_missing(self):
        assert not self.filter.matches({"not": {"the": {"key": "to match"}}})

    def test_different_objects_with_same_expected_value_are_equal(self):
        assert id(self.filter) != id(self.filter_identical)
        assert self.filter == self.filter_identical

    # pylint: enable=no-member


class TestStringFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.expected_value = "expected value"
        self.filter = StringFilterExpression(["key1", "key2"], self.expected_value)
        self.filter_identical = StringFilterExpression(["key1", "key2"], self.expected_value)

    def test_string_representation(self):
        assert str(self.filter) == f'key1.key2:"{self.expected_value}"'

    def test_does_not_match_if_string_is_not_identical(self):
        assert not self.filter.matches({"key1": {"key2": "test"}})

    def test_does_not_match_if_string_representation_is_not_identical(self):
        filter = StringFilterExpression(["key1", "key2"], "2.0")
        assert not filter.matches({"key1": {"key2": 2}})

    def test_matches_if_string_is_identical(self):
        assert self.filter.matches({"key1": {"key2": self.expected_value}})

    def test_matches_if_string_representation_is_identical(self):
        filter = StringFilterExpression(["key1", "key2"], "2")
        assert filter.matches({"key1": {"key2": 2}})


class TestIntegerFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.expected_value = 42
        self.filter = IntegerFilterExpression(["key1", "key2"], self.expected_value)
        self.filter_identical = IntegerFilterExpression(["key1", "key2"], self.expected_value)

    def test_string_representation(self):
        assert str(self.filter) == f"key1.key2:{self.expected_value:d}"

    def test_does_not_match_if_value_is_not_identical(self):
        assert not self.filter.matches({"key1": {"key2": 23}})

    def test_does_not_match_when_value_is_identical_but_as_float(self):
        assert self.filter.matches({"key1": {"key2": float(self.expected_value)}})

    def test_does_match_when_value_is_identical(self):
        assert self.filter.matches({"key1": {"key2": self.expected_value}})


class TestFloatFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.expected_value = 42.0
        self.filter = FloatFilterExpression(["key1", "key2"], self.expected_value)
        self.filter_identical = FloatFilterExpression(["key1", "key2"], self.expected_value)

    def test_string_representation(self):
        assert str(self.filter) == f"key1.key2:{self.expected_value:0.1f}"

    def test_does_not_match_if_value_is_not_identical(self):
        assert not self.filter.matches({"key1": {"key2": 23.0}})

    def test_does_not_match_when_value_is_identical_but_as_integer(self):
        assert self.filter.matches({"key1": {"key2": int(self.expected_value)}})

    def test_does_match_when_value_is_identical(self):
        assert self.filter.matches({"key1": {"key2": self.expected_value}})


class TestIntegerRangeFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.filter = IntegerRangeFilterExpression(["key1", "key2"], 23, 42)
        self.filter_identical = IntegerRangeFilterExpression(["key1", "key2"], 23, 42)

    def test_string_representation(self):
        assert str(self.filter) == "key1.key2:[23 TO 42]"

    def test_does_not_match_if_value_is_below_lower_bound(self):
        assert not self.filter.matches({"key1": {"key2": 23 - 1}})

    def test_does_not_match_if_value_is_above_upper_bound(self):
        assert not self.filter.matches({"key1": {"key2": 42 + 1}})

    def test_does_not_match_when_value_is_in_range_but_as_float(self):
        assert self.filter.matches({"key1": {"key2": 24.0}})

    def test_does_match_when_value_is_in_range(self):
        for i in range(23, 43):
            assert self.filter.matches({"key1": {"key2": i}})


class TestFloatRangeFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.filter = FloatRangeFilterExpression(["key1", "key2"], 23.0, 42.0)
        self.filter_identical = FloatRangeFilterExpression(["key1", "key2"], 23.0, 42.0)

    def test_string_representation(self):
        assert str(self.filter) == "key1.key2:[23.0 TO 42.0]"

    def test_does_not_match_if_value_is_below_lower_bound(self):
        assert not self.filter.matches({"key1": {"key2": 23.0 - 1.0}})

    def test_does_not_match_if_value_is_above_upper_bound(self):
        assert not self.filter.matches({"key1": {"key2": 42.0 + 1.0}})

    def test_does_match_when_value_is_in_range(self):
        for i in range(23, 43):
            assert self.filter.matches({"key1": {"key2": float(i)}})


class TestRegExFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.regex = "start.*end"
        self.filter = RegExFilterExpression(["key1", "key2"], self.regex)
        self.filter_identical = RegExFilterExpression(["key1", "key2"], self.regex)

    def test_string_representation(self):
        assert str(self.filter) == "key1.key2:r/^start.*end$/"

    def test_does_not_match_if_key_is_missing(self):
        assert not self.filter.matches({"not": {"the": {"key": "to match"}}})

    def test_empty_regex_matches_nothing(self):
        filter = RegExFilterExpression(["key1", "key2"], "")
        for length in range(1, 20):
            assert not filter.matches(
                {"key1": {"key2": "".join(sample(digits + ascii_letters, length))}}
            )

    def test_empty_regex_matches_empty_content(self):
        filter = RegExFilterExpression(["key1", "key2"], "")
        assert filter.matches({"key1": {"key2": ""}})

    def test_regex_matches_anything_at_wildcard(self):
        for length in range(0, 20):
            assert self.filter.matches(
                {
                    "key1": {
                        "key2": "start" + "".join(sample(digits + ascii_letters, length)) + "end"
                    }
                }
            )


class TestExistsFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.split_field = ["key1", "key2"]
        self.filter = Exists(["key1", "key2"])
        self.filter_identical = Exists(["key1", "key2"])

    def test_string_representation(self):
        assert str(self.filter) == '"key1.key2"'

    def test_matches_any_value(self):
        filter = Exists(["key1", "key2"])
        assert filter.matches({"key1": {"key2": ""}})
        assert filter.matches({"key1": {"key2": "foo"}})
        assert filter.matches({"key1": {"key2": "bar"}})

    def test_does_not_match_if_value_matches_key(self):
        filter = Exists(["key1", "key2"])
        assert filter.matches({"key1": "key2"}) is False


class TestWildcardFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.value = "start*end"
        self.filter = WildcardStringFilterExpression(["key1", "key2"], self.value)
        self.filter_identical = WildcardStringFilterExpression(["key1", "key2"], self.value)

    def test_string_representation(self):
        assert str(self.filter) == 'key1.key2:"start*end"'

    def test_does_not_match_if_key_is_missing(self):
        assert not self.filter.matches({"not": {"the": {"key": "to match"}}})

    def test_empty_value_matches_nothing(self):
        filter = WildcardStringFilterExpression(["key1", "key2"], "")
        for length in range(1, 20):
            assert not filter.matches(
                {"key1": {"key2": "".join(sample(digits + ascii_letters, length))}}
            )

    def test_empty_value_matches_empty_content(self):
        filter = WildcardStringFilterExpression(["key1", "key2"], "")
        assert filter.matches({"key1": {"key2": ""}})

    def test_matches_case_sensitive(self):
        assert self.filter.matches({"key1": {"key2": "startXend"}})
        assert not self.filter.matches({"key1": {"key2": "StartXend"}})

    def test_matches_anything_at_star_wildcard(self):
        for length in range(0, 20):
            assert self.filter.matches(
                {
                    "key1": {
                        "key2": "start" + "".join(sample(digits + ascii_letters, length)) + "end"
                    }
                }
            )

    def test_matches_anything_at_questionmark_wildcard(self):
        self.value = "start?end"
        self.filter = WildcardStringFilterExpression(["key1", "key2"], self.value)
        self.filter_identical = WildcardStringFilterExpression(["key1", "key2"], self.value)

        assert self.filter.matches({"key1": {"key2": "startend"}})
        for _ in range(0, 20):
            assert self.filter.matches(
                {"key1": {"key2": "start" + "".join(sample(digits + ascii_letters, 1)) + "end"}}
            )
        for length in range(2, 20):
            assert not self.filter.matches(
                {
                    "key1": {
                        "key2": "start" + "".join(sample(digits + ascii_letters, length)) + "end"
                    }
                }
            )


class TestSigmaFilterExpression(ValueBasedFilterExpressionTest):
    def setup_method(self, _):
        self.value = "start*end"
        self.filter = SigmaFilterExpression(["key1", "key2"], self.value)
        self.filter_identical = SigmaFilterExpression(["key1", "key2"], self.value)

    def test_string_representation(self):
        assert str(self.filter) == 'key1.key2:"start*end"'

    def test_does_not_match_if_key_is_missing(self):
        assert not self.filter.matches({"not": {"the": {"key": "to match"}}})

    def test_empty_value_matches_nothing(self):
        filter = SigmaFilterExpression(["key1", "key2"], "")
        for length in range(1, 20):
            assert not filter.matches(
                {"key1": {"key2": "".join(sample(digits + ascii_letters, length))}}
            )

    def test_empty_value_matches_empty_content(self):
        filter = SigmaFilterExpression(["key1", "key2"], "")
        assert filter.matches({"key1": {"key2": ""}})

    def test_matches_case_insensitive(self):
        assert self.filter.matches({"key1": {"key2": "startXend"}})
        assert self.filter.matches({"key1": {"key2": "StartXend"}})

    def test_matches_anything_at_star_wildcard(self):
        for length in range(0, 20):
            assert self.filter.matches(
                {
                    "key1": {
                        "key2": "start" + "".join(sample(digits + ascii_letters, length)) + "end"
                    }
                }
            )

    def test_matches_anything_at_questionmark_wildcard(self):
        self.value = "start?end"
        self.filter = SigmaFilterExpression(["key1", "key2"], self.value)
        self.filter_identical = SigmaFilterExpression(["key1", "key2"], self.value)

        assert self.filter.matches({"key1": {"key2": "startend"}})
        for _ in range(0, 20):
            assert self.filter.matches(
                {"key1": {"key2": "start" + "".join(sample(digits + ascii_letters, 1)) + "end"}}
            )
        for length in range(2, 20):
            assert not self.filter.matches(
                {
                    "key1": {
                        "key2": "start" + "".join(sample(digits + ascii_letters, length)) + "end"
                    }
                }
            )
