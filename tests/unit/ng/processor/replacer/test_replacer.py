# pylint: disable=missing-docstring
# pylint: disable=protected-access
from unittest import mock

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.replacer.rule import Replacement
from tests.unit.ng.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "replace the beginning",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
    ),
    (
        "replace with a different target field",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{X} login attempts."},
                "target_field": "new_target",
            },
        },
        {"field": "123 login attempts."},
        {"field": "123 login attempts.", "new_target": "X login attempts."},
    ),
    (
        "replace with dotted field",
        {
            "filter": "some.field",
            "replacer": {
                "mapping": {"some.field": "%{X} login attempts."},
            },
        },
        {"some": {"field": "123 login attempts."}},
        {"some": {"field": "X login attempts."}},
    ),
    (
        "replace with colon notation",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*:X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
    ),
    (
        "replace wildcard with colon notation",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*:*} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "123 login attempts."},
    ),
    (
        "replace specific with colon notation matches",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
    ),
    (
        "replace specific with colon notation at beginning does not match",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts by %{USER_ID}."},
            },
        },
        {"field": "456 login attempts by 789."},
        {"field": "456 login attempts by 789."},
    ),
    (
        "replace specific with colon notation at beginning matches",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts by %{USER_ID}."},
            },
        },
        {"field": "123 login attempts by 789."},
        {"field": "X login attempts by USER_ID."},
    ),
    (
        "replace specific with colon notation at middle does not match",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} performed %{789:X} login attempts."},
            },
        },
        {"field": "User 123 performed 456 login attempts."},
        {"field": "User 123 performed 456 login attempts."},
    ),
    (
        "replace specific with colon notation at middle matches",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} performed %{456:X} login attempts."},
            },
        },
        {"field": "User 123 performed 456 login attempts."},
        {"field": "User USER_ID performed X login attempts."},
    ),
    (
        "replace specific with colon notation at end does not match",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} login count: %{789:X}"},
            },
        },
        {"field": "User 123 login count: 456"},
        {"field": "User 123 login count: 456"},
    ),
    (
        "replace specific with colon notation at end matches",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} login count: %{456:X}"},
            },
        },
        {"field": "User 123 login count: 456"},
        {"field": "User USER_ID login count: X"},
    ),
    (
        "replace specific with colon notation matches combined without colon notation",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts within %{Y} minutes."},
            },
        },
        {"field": "123 login attempts within 456 minutes."},
        {"field": "X login attempts within Y minutes."},
    ),
    (
        "replace specific with colon notation matches combined without colon notation",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "/%{*}/foo/%{_:}%{ID}/%{*}"},
            },
        },
        {"field": "/some/path/foo/_123/bar"},
        {"field": "/some/path/foo/ID/bar"},
    ),
    (
        "replace specific with colon notation starting with wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*}/%{_:}%{ID}/%{*}"},
            },
        },
        {"field": "/some/path/foo/_123/bar"},
        {"field": "/some/path/foo/ID/bar"},
    ),
    (
        "replace specific with colon notation without wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "/some/path/%{_:}%{ID}"},
            },
        },
        {"field": "/some/path/_123"},
        {"field": "/some/path/ID"},
    ),
    (
        "replace the middle",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Attempted to login %{X} times."},
            },
        },
        {"field": "Attempted to login 123 times."},
        {"field": "Attempted to login X times."},
    ),
    (
        "replace the end",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Delete user %{USER_ID}"},
            },
        },
        {"field": "Delete user 123"},
        {"field": "Delete user USER_ID"},
    ),
    (
        "replace beginning and the middle",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{A user} tried to call /users/%{USER_ID}/delete"},
            },
        },
        {"field": "User 123 tried to call /users/456/delete"},
        {"field": "A user tried to call /users/USER_ID/delete"},
    ),
    (
        "replace twice in middle",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} tried %{ATTEMPTS} times to log in."},
            },
        },
        {"field": "User 123 tried 456 times to log in."},
        {"field": "User USER_ID tried ATTEMPTS times to log in."},
    ),
    (
        "replace the middle and the end",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Attempted to login %{ATTEMPTS} times to %{IP}"},
            },
        },
        {"field": "Attempted to login 123 times to 1.2.3.4"},
        {"field": "Attempted to login ATTEMPTS times to IP"},
    ),
    (
        "replace three times",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} tried to login %{ATTEMPTS} to %{IP}"},
            },
        },
        {"field": "User 123 tried to login 456 to 1.2.3.4"},
        {"field": "User USER_ID tried to login ATTEMPTS to IP"},
    ),
    (
        "replace with empty string",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{}login attempts%{}."},
            },
        },
        {"field": "123 login attempts by user 456."},
        {"field": "login attempts."},
    ),
    (
        "don't replace greedily if part of variable string is contained in unchanging part",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Connected to %{IP|g}."},
            },
        },
        {"field": "Connected to 1.2.3.4."},
        {"field": "Connected to IP."},
    ),
    (
        "twice don't replace greedily if part of variable string is contained in unchanging part",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Disconnected from %{IP|g}. Connected to %{IP|g}."},
            },
        },
        {"field": "Disconnected from 1.2.3.4. Connected to 1.2.3.4."},
        {"field": "Disconnected from IP. Connected to IP."},
    ),
    (
        "replace wildcard greedily",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Disconnected from %{IP|g}. Connected to %{*|g}."},
            },
        },
        {"field": "Disconnected from 1.2.3.4. Connected to 1.2.3.4."},
        {"field": "Disconnected from IP. Connected to 1.2.3.4."},
    ),
    (
        "replace multiple fields",
        {
            "filter": "field_a AND field_b",
            "replacer": {
                "mapping": {
                    "field_a": "do %{replace this}!",
                    "field_b": "do also %{replace this}!",
                },
            },
        },
        {"field_a": "do something!", "field_b": "do also something!"},
        {"field_a": "do replace this!", "field_b": "do also replace this!"},
    ),
    (
        "replace by matching with wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has%{*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
    ),
    (
        "replace by matching only with wildcard does not change anything",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User has logged %{*}."},
            },
        },
        {"field": "User has logged in."},
        {"field": "User has logged in."},
    ),
    (
        "replace by matching with wildcard at the end",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
    ),
    (
        "replace by matching with wildcard at the beginning",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*} with ID %{USER_ID} has logged in."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
    ),
    (
        "replace by matching with wildcard in the middle before other replacement",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{*} with ID %{USER_ID} has logged in."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
    ),
    (
        "replace by matching with multiple wildcards",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*} with ID %{USER_ID} has %{*}in%{*}"},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
    ),
    (
        "replace with star by escaping single wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{\\*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged *."},
    ),
    (
        "replace with backslash and star by escaping single wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has%{\\\\*}"},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has\\*"},
    ),
    (
        "replace with multiple backslashes and star by escaping single wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{\\\\\\*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged \\\\*."},
    ),
    (
        "replacement of multiple stars does not require escaping wildcard",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{**}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged **."},
    ),
    (
        "replacement without matching end fails",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Call /some_path/user/%{USER_ID}/"},
            },
        },
        {"field": "Call /some_path/user/123/delete"},
        {"field": "Call /some_path/user/123/delete"},
    ),
    (
        "replacement without matching beginning fails",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "failed logins: %{COUNT}"},
            },
        },
        {"field": "logins: 123"},
        {"field": "logins: 123"},
    ),
    (
        "replacement without matching beginning and end fails",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "failed to login %{COUNT} times during the last hour"},
            },
        },
        {"field": "succeeded to login 123 times during the last minute"},
        {"field": "succeeded to login 123 times during the last minute"},
    ),
    (
        "replacement without matching middle fails",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{USER} created by %{USER}"},
            },
        },
        {"field": "123 deleted by 456"},
        {"field": "123 deleted by 456"},
    ),
    (
        "nested replacement ignores second start token and terminates with first end token",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{%{replace this} not}!"},
            },
        },
        {"field": "something not}!"},
        {"field": "%{replace this not}!"},
    ),
    (
        "nested replacement ignores second start token and terminates with first end token",
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{do %{replace this}}!"},
            },
        },
        {"field": "do %{something not}!"},
        {"field": "do %{replace this}!"},
    ),
]


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
