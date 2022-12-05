# pylint: disable=missing-docstring

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": 1278},
    ),
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss ZZ} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "2013-05-09 03:56:47 -03:00", "field1": "2022-12-05"},
        {"field2": "2013-05-09 03:56:47 -03:00", "field1": "2022-12-05", "time_diff": 25007},
    ),
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:dddd, DD. MMMM YYYY HH:mmA} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Monday, 05. December 2022 11:19AM", "field1": "2022-12-05"},
        {"field2": "Monday, 05. December 2022 11:19AM", "field1": "2022-12-05", "time_diff": 40740},
    ),
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:ddd MMM D H:mm:ss A YYYY} - ${field1:YYYY-MM-DD}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-05"},
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-05", "time_diff": 47671},
    ),
    (
        "diff between two timestamps",
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
            "time_diff": 44071,
        },
    ),
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
                "output_format": "milliseconds",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": 1278000},
    ),
    (
        "diff between two timestamps",
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
            "time_diff": 1278000000000,
        },
    ),
    (
        "diff between two timestamps",
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
            "time_diff": 1278,
        },
    ),
    (
        "diff between two timestamps",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "time_diff": 1278,
        },
    ),
]


validation_failure_test_cases = [  # testcase, rule, event, expected, error_message
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
]

failure_test_cases = [  # testcase, rule, event, expected, error_message
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} + ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} something ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
    (
        "Tags failure if parse is not possible",
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
        },
        r"'diff' must match regex",
    ),
]


class TestTimestampDiffer(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "timestamp_differ",
        "specific_rules": ["tests/testdata/unit/timestamp_differ/specific_rules"],
        "generic_rules": ["tests/testdata/unit/timestamp_differ/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning, match=error_message):
            self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", validation_failure_test_cases)
    def test_testcases_validation_failures(self, testcase, rule, event, expected, error_message):
        with pytest.raises(ValueError, match=error_message):
            self._load_specific_rule(rule)
            self.object.process(event)
        assert event == expected, testcase
