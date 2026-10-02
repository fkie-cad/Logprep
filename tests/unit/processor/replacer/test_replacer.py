# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

from unittest import mock

import pytest

from logprep.processor.replacer.rule import Replacement
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [  # rule, event, expected
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
        id="replace the beginning",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{X} login attempts."},
                "target_field": "new_target",
            },
        },
        {"field": "123 login attempts."},
        {"field": "123 login attempts.", "new_target": "X login attempts."},
        id="replace with a different target field",
    ),
    pytest.param(
        {
            "filter": "some.field",
            "replacer": {
                "mapping": {"some.field": "%{X} login attempts."},
            },
        },
        {"some": {"field": "123 login attempts."}},
        {"some": {"field": "X login attempts."}},
        id="replace with dotted field",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*:X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
        id="replace with colon notation",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*:*} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "123 login attempts."},
        id="replace wildcard with colon notation",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts."},
            },
        },
        {"field": "123 login attempts."},
        {"field": "X login attempts."},
        id="replace specific with colon notation matches",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts by %{USER_ID}."},
            },
        },
        {"field": "456 login attempts by 789."},
        {"field": "456 login attempts by 789."},
        id="replace specific with colon notation at beginning does not match",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts by %{USER_ID}."},
            },
        },
        {"field": "123 login attempts by 789."},
        {"field": "X login attempts by USER_ID."},
        id="replace specific with colon notation at beginning matches",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} performed %{789:X} login attempts."},
            },
        },
        {"field": "User 123 performed 456 login attempts."},
        {"field": "User 123 performed 456 login attempts."},
        id="replace specific with colon notation at middle does not match",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} performed %{456:X} login attempts."},
            },
        },
        {"field": "User 123 performed 456 login attempts."},
        {"field": "User USER_ID performed X login attempts."},
        id="replace specific with colon notation at middle matches",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} login count: %{789:X}"},
            },
        },
        {"field": "User 123 login count: 456"},
        {"field": "User 123 login count: 456"},
        id="replace specific with colon notation at end does not match",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} login count: %{456:X}"},
            },
        },
        {"field": "User 123 login count: 456"},
        {"field": "User USER_ID login count: X"},
        id="replace specific with colon notation at end matches",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{123:X} login attempts within %{Y} minutes."},
            },
        },
        {"field": "123 login attempts within 456 minutes."},
        {"field": "X login attempts within Y minutes."},
        id="replace specific with colon notation matches combined without colon notation",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "/%{*}/foo/%{_:}%{ID}/%{*}"},
            },
        },
        {"field": "/some/path/foo/_123/bar"},
        {"field": "/some/path/foo/ID/bar"},
        id="replace specific with colon notation matches combined without colon notation",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*}/%{_:}%{ID}/%{*}"},
            },
        },
        {"field": "/some/path/foo/_123/bar"},
        {"field": "/some/path/foo/ID/bar"},
        id="replace specific with colon notation starting with wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "/some/path/%{_:}%{ID}"},
            },
        },
        {"field": "/some/path/_123"},
        {"field": "/some/path/ID"},
        id="replace specific with colon notation without wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Attempted to login %{X} times."},
            },
        },
        {"field": "Attempted to login 123 times."},
        {"field": "Attempted to login X times."},
        id="replace the middle",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Delete user %{USER_ID}"},
            },
        },
        {"field": "Delete user 123"},
        {"field": "Delete user USER_ID"},
        id="replace the end",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{A user} tried to call /users/%{USER_ID}/delete"},
            },
        },
        {"field": "User 123 tried to call /users/456/delete"},
        {"field": "A user tried to call /users/USER_ID/delete"},
        id="replace beginning and the middle",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} tried %{ATTEMPTS} times to log in."},
            },
        },
        {"field": "User 123 tried 456 times to log in."},
        {"field": "User USER_ID tried ATTEMPTS times to log in."},
        id="replace twice in middle",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Attempted to login %{ATTEMPTS} times to %{IP}"},
            },
        },
        {"field": "Attempted to login 123 times to 1.2.3.4"},
        {"field": "Attempted to login ATTEMPTS times to IP"},
        id="replace the middle and the end",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{USER_ID} tried to login %{ATTEMPTS} to %{IP}"},
            },
        },
        {"field": "User 123 tried to login 456 to 1.2.3.4"},
        {"field": "User USER_ID tried to login ATTEMPTS to IP"},
        id="replace three times",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{}login attempts%{}."},
            },
        },
        {"field": "123 login attempts by user 456."},
        {"field": "login attempts."},
        id="replace with empty string",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Connected to %{IP|g}."},
            },
        },
        {"field": "Connected to 1.2.3.4."},
        {"field": "Connected to IP."},
        id="don't replace greedily if part of variable string is contained in unchanging part",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Disconnected from %{IP|g}. Connected to %{IP|g}."},
            },
        },
        {"field": "Disconnected from 1.2.3.4. Connected to 1.2.3.4."},
        {"field": "Disconnected from IP. Connected to IP."},
        id="twice don't replace greedily if part of variable string is contained in unchanging part",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Disconnected from %{IP|g}. Connected to %{*|g}."},
            },
        },
        {"field": "Disconnected from 1.2.3.4. Connected to 1.2.3.4."},
        {"field": "Disconnected from IP. Connected to 1.2.3.4."},
        id="replace wildcard greedily",
    ),
    pytest.param(
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
        id="replace multiple fields",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has%{*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
        id="replace by matching with wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User has logged %{*}."},
            },
        },
        {"field": "User has logged in."},
        {"field": "User has logged in."},
        id="replace by matching only with wildcard does not change anything",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
        id="replace by matching with wildcard at the end",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*} with ID %{USER_ID} has logged in."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
        id="replace by matching with wildcard at the beginning",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User %{*} with ID %{USER_ID} has logged in."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
        id="replace by matching with wildcard in the middle before other replacement",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{*} with ID %{USER_ID} has %{*}in%{*}"},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged in."},
        id="replace by matching with multiple wildcards",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{\\*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged *."},
        id="replace with star by escaping single wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has%{\\\\*}"},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has\\*"},
        id="replace with backslash and star by escaping single wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{\\\\\\*}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged \\\\*."},
        id="replace with multiple backslashes and star by escaping single wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "User with ID %{USER_ID} has logged %{**}."},
            },
        },
        {"field": "User with ID 123 has logged in."},
        {"field": "User with ID USER_ID has logged **."},
        id="replacement of multiple stars does not require escaping wildcard",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "Call /some_path/user/%{USER_ID}/"},
            },
        },
        {"field": "Call /some_path/user/123/delete"},
        {"field": "Call /some_path/user/123/delete"},
        id="replacement without matching end fails",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "failed logins: %{COUNT}"},
            },
        },
        {"field": "logins: 123"},
        {"field": "logins: 123"},
        id="replacement without matching beginning fails",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "failed to login %{COUNT} times during the last hour"},
            },
        },
        {"field": "succeeded to login 123 times during the last minute"},
        {"field": "succeeded to login 123 times during the last minute"},
        id="replacement without matching beginning and end fails",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{USER} created by %{USER}"},
            },
        },
        {"field": "123 deleted by 456"},
        {"field": "123 deleted by 456"},
        id="replacement without matching middle fails",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{%{replace this} not}!"},
            },
        },
        {"field": "something not}!"},
        {"field": "%{replace this not}!"},
        id="nested replacement ignores second start token and terminates with first end token",
    ),
    pytest.param(
        {
            "filter": "field",
            "replacer": {
                "mapping": {"field": "%{do %{replace this}}!"},
            },
        },
        {"field": "do %{something not}!"},
        {"field": "do %{replace this}!"},
        id="nested replacement ignores second start token and terminates with first end token",
    ),
)


class TestReplacer(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "replacer",
        "rules": ["tests/testdata/unit/replacer/rules_1", "tests/testdata/unit/replacer/rules_2"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

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
        self.object.process(event)
        assert event == expected

    @mock.patch("logprep.processor.replacer.processor.Replacer._handle_wildcard", return_value=None)
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
        self.object.process(event)
        assert event == expected

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
        second_replacement = replacements[1]
        second_replacement.match = "exists and does not match"
        self.object.process(event)
        assert event == expected

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
