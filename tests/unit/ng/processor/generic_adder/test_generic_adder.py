# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=unused-argument
# pylint: disable=too-many-arguments

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestGenericAdder(BaseProcessorTestCase):
    test_cases = [  # testcase, rule, event, expected
        (
            "Add from file",
            {
                "filter": "add_list_generic_test",
                "generic_adder": {
                    "add_from_file": "tests/testdata/unit/generic_adder/additions_file.yml"
                },
            },
            {"add_list_generic_test": "Test", "event_id": 123},
            {
                "add_list_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from file in list",
            {
                "filter": "add_lists_one_generic_test",
                "generic_adder": {
                    "add_from_file": ["tests/testdata/unit/generic_adder/additions_file.yml"]
                },
            },
            {"add_lists_one_generic_test": "Test", "event_id": 123},
            {
                "add_lists_one_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
    ]

    CONFIG = {
        "type": "ng_generic_adder",
        "rules": ["tests/testdata/unit/generic_adder/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected, testcase
