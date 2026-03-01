# pylint: disable=missing-docstring
# pylint: disable=protected-access
from copy import deepcopy
from unittest import mock

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.replacer.rule import Replacement
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.replacer.test_replacer import test_cases as non_ng_test_cases

test_cases = deepcopy(non_ng_test_cases)


class TestReplacer(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_replacer",
        "rules": ["tests/testdata/unit/replacer/rules_1", "tests/testdata/unit/replacer/rules_2"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected, testcase

    def test_template_is_none_does_nothing(self):
        rule = {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{replace this}"},
            },
        }
        event = {"field": "anything"}
        expected = {"field": "anything"}
        self._load_rule(rule)
        self.object.rules[0].templates["field"] = None
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected

    @mock.patch(
        "logprep.ng.processor.replacer.processor.Replacer._handle_wildcard", return_value=None
    )
    def test_replacement_is_none_does_nothing(self, _):
        rule = {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{replace this}"},
            },
        }
        event = {"field": "anything"}
        expected = {"field": "anything"}
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected

    def test_not_first_match_is_not_none_but_does_not_match_does_nothing(self):
        rule = {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{replace this} and %{also this}"},
            },
        }
        event = {"field": "anything and something"}
        expected = {"field": "anything and something"}
        self._load_rule(rule)
        replacements = self.object.rules[0].templates["field"].replacements
        second_replacement = replacements[1]._asdict()
        second_replacement["match"] = "exists and does not match"
        replacements[1] = Replacement(**second_replacement)
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected

    def test_handle_wildcard_keep_original_without_matching_next_returns_none(self):
        replacement = Replacement(
            value="anything",
            next="does not match",
            match=None,
            keep_original=True,
            greedy=False,
        )
        result = self.object._handle_wildcard(replacement, "something")
        assert result is None
