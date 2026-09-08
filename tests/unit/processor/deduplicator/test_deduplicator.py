# pylint: disable=missing-docstring
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
import pytest

from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    pytest.param(
        {
            "filter": "remove_duplicate_str",
            "deduplicator": {"fields": ["remove_duplicate_str"]},
        },
        {"remove_duplicate_str": ["foo", "bar", "foo"]},
        {"remove_duplicate_str": ["foo", "bar"]},
        id="remove_duplicate_str",
    ),
    pytest.param(
        {
            "filter": "remove_duplicate_int",
            "deduplicator": {"fields": ["remove_duplicate_int"]},
        },
        {"remove_duplicate_int": [1, 2, 1, 2, 2, 1]},
        {"remove_duplicate_int": [1, 2]},
        id="remove_duplicate_int",
    ),
    pytest.param(
        {
            "filter": "remove_duplicate_dict",
            "deduplicator": {"fields": ["remove_duplicate_dict"]},
        },
        {"remove_duplicate_dict": [{"a": {"b": "c"}}, {"a": {"b": "c"}}, {"foo": "bar"}]},
        {"remove_duplicate_dict": [{"a": {"b": "c"}}, {"foo": "bar"}]},
        id="remove_duplicate_dict",
    ),
    pytest.param(
        {
            "filter": "fields_1 AND fields_2",
            "deduplicator": {"fields": ["fields_1", "fields_2"]},
        },
        {"fields_1": ["foo", "bar", "foo"], "fields_2": ["baz", "baz"]},
        {"fields_1": ["foo", "bar"], "fields_2": ["baz"]},
        id="remove_from_multiple_fields",
    ),
]
test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "do_nothing",
            "deduplicator": {},
        },
        {"remove_duplicates": ["foo", "bar", "foo"], "keep": ["foo", "foo"]},
        {"remove_duplicates": ["foo", "bar", "foo"], "keep": ["foo", "foo"]},
        id="do_nothing",
    ),
    pytest.param(
        {
            "filter": "no_fields",
            "deduplicator": {"fields": []},
        },
        {"no_fields": ["foo", "bar", "foo"]},
        {"no_fields": ["foo", "bar", "foo"]},
        id="rule_no_fields",
    ),
    pytest.param(
        {
            "filter": "no_matching_fields",
            "deduplicator": {"fields": ["no_matching_fields"]},
        },
        {"fields": ["foo", "bar", "foo"]},
        {"fields": ["foo", "bar", "foo"]},
        id="no_matching_fields",
    ),
    pytest.param(
        {
            "filter": "no_list",
            "deduplicator": {"fields": ["no_list"]},
        },
        {"no_list": "aa"},
        {"no_list": "aa"},
        id="no_list",
    ),
)


class TestDeduplicator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "deduplicator",
        "rules": ["tests/testdata/unit/deduplicator/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected
