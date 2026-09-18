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
        id="replace_the_beginning",
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
        id="replace_with_a_different_target_field",
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
        id="replace_with_dotted_field",
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
        id="replace_with_colon_notation",
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
        id="replace_wildcard_with_colon_notation",
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
        id="replace_specific_with_colon_notation_matches",
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
        id="replace_specific_with_colon_notation_at_beginning_does_not_match",
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
        id="replace_specific_with_colon_notation_at_beginning_matches",
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
        id="replace_specific_with_colon_notation_at_middle_does_not_match",
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
        id="replace_specific_with_colon_notation_at_middle_matches",
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
        id="replace_specific_with_colon_notation_at_end_does_not_match",
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
        id="replace_specific_with_colon_notation_at_end_matches",
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
        id="replace_specific_with_colon_notation_matches_combined_without_colon_notation",
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
        id="replace_specific_with_colon_notation_matches_combined_without_colon_notation",
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
        id="replace_specific_with_colon_notation_starting_with_wildcard",
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
        id="replace_specific_with_colon_notation_without_wildcard",
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
        id="replace_the_middle",
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
        id="replace_the_end",
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
        id="replace_beginning_and_the_middle",
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
        id="replace_twice_in_middle",
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
        id="replace_the_middle_and_the_end",
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
        id="replace_three_times",
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
        id="replace_with_empty_string",
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
        id="don't_replace_greedily_if_part_of_variable_string_is_contained_in_unchanging_part",
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
        id="twice_don't_replace_greedily_if_part_of_variable_string_is_contained_in_unchanging_part",
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
        id="replace_wildcard_greedily",
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
        id="replace_multiple_fields",
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
        id="replace_by_matching_with_wildcard",
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
        id="replace_by_matching_only_with_wildcard_does_not_change_anything",
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
        id="replace_by_matching_with_wildcard_at_the_end",
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
        id="replace_by_matching_with_wildcard_at_the_beginning",
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
        id="replace_by_matching_with_wildcard_in_the_middle_before_other_replacement",
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
        id="replace_by_matching_with_multiple_wildcards",
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
        id="replace_with_star_by_escaping_single_wildcard",
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
        id="replace_with_backslash_and_star_by_escaping_single_wildcard",
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
        id="replace_with_multiple_backslashes_and_star_by_escaping_single_wildcard",
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
        id="replacement_of_multiple_stars_does_not_require_escaping_wildcard",
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
        id="replacement_without_matching_end_fails",
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
        id="replacement_without_matching_beginning_fails",
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
        id="replacement_without_matching_beginning_and_end_fails",
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
        id="replacement_without_matching_middle_fails",
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
        id="nested_replacement_ignores_second_start_token_and_terminates_with_first_end_token",
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
        id="nested_replacement_ignores_second_start_token_and_terminates_with_first_end_token",
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
