# pylint: disable=missing-docstring

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "Time difference between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": "1278 s"},
    ),
    (
        "Time difference between two timestamps with timezone information",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss ZZ} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "2013-05-09 03:56:47 -03:00", "field1": "2022-12-05"},
        {"field2": "2013-05-09 03:56:47 -03:00", "field1": "2022-12-05", "time_diff": "25007 s"},
    ),
    (
        "Time difference between two timestamps with full weekday and month",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:dddd, DD. MMMM YYYY HH:mmA} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Monday, 05. December 2022 11:19AM", "field1": "2022-12-05"},
        {"field2": "Monday, 05. December 2022 11:19AM", "field1": "2022-12-05", "time_diff": "40740 s"},
    ),
    (
        "Time difference between two timestamps with AM/PM ",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:ddd MMM D H:mm:ss A YYYY} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-05"},
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-05", "time_diff": "47671 s"},
    ),
    (
        "Time difference between two timestamps with timezone name",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:ddd MMM D H:mm:ss A YYYY ZZZ} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Wed Dec 4 1:14:31 PM 2022 Europe/Warsaw", "field1": "2022-12-05"},
        {
            "field2": "Wed Dec 4 1:14:31 PM 2022 Europe/Warsaw",
            "field1": "2022-12-05",
            "time_diff": "44071 s",
        },
    ),
    (
        "Time difference between two timestamps with milliseconds output",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
                "output_format": "milliseconds",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": "1278000 ms"},
    ),
    (
        "Time difference between two timestamps with nanoseconds output",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
                "output_format": "nanoseconds",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278000000000 ns",
        },
    ),
    (
        "Time difference between two timestamps in subfield",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "time_diff": "1278 s",
        },
    ),
    (
        "Time difference between two timestamps without specific timestamp format",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 12:00:00", "subfield": {"field2": "2022-12-05T11:38:42+02:00"}},
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42+02:00"},
            "time_diff": "77922 s",
        },
    ),
]

failure_test_cases = [  # testcase, rule, event, expected, error_message
    (
        "Timestamp diff with integer field (does not match default timestamp format)",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": 15, "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": 15,
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "tags": ["_timestamp_differ_failure"],
        },
        r"Failed to match 'YYYY-MM-DDTHH:mm:ssZZ' when parsing",
    ),
    (
        "Timestamp diff with string field",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": "non-timestamp", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "non-timestamp",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "tags": ["_timestamp_differ_failure"],
        },
        r"Failed to match 'YYYY-MM-DDTHH:mm:ssZZ' when parsing",
    ),
    (
        "diff between two timestamps with partial timestamp format match",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "tags": ["_timestamp_differ_failure"],
        },
        "Failed to match 'YYYY-MM-DD HH:mm:ss' when parsing",
    ),
]


class TestTimestampDiffer(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "timestamp_differ",
        "specific_rules": ["tests/testdata/unit/timestamp_differ/specific_rules"],
        "generic_rules": ["tests/testdata/unit/timestamp_differ/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning, match=error_message):
            self.object.process(event)
        assert event == expected, testcase
