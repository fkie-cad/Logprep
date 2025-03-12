# pylint: disable=missing-docstring
import pytest

from tests.unit.processor.base import BaseProcessorTestCase

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
                "mapping": {"field": "Connected to %{IP}."},
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
                "mapping": {"field": "Disconnected from %{IP}. Connected to %{IP}."},
            },
        },
        {"field": "Disconnected from 1.2.3.4. Connected to 1.2.3.4."},
        {"field": "Disconnected from IP. Connected to IP."},
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
        "type": "replacer",
        "rules": ["tests/testdata/unit/replacer/rules_1", "tests/testdata/unit/replacer/rules_2"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected, testcase
