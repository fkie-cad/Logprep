# pylint: disable=missing-docstring,too-many-arguments,too-many-positional-arguments
import re

import pytest

from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": "1278.0"},
        id="Time difference between two timestamps",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-04 12:00:00", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-04 12:00:00",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "86400.0",
        },
        id="Time difference between two timestamps with day change",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S %z} - ${field1:%Y-%m-%d}",
                "target_field": "time_diff",
            },
        },
        {"field2": "2022-05-09 03:56:47 -03:00", "field1": "2022-05-08"},
        {"field2": "2022-05-09 03:56:47 -03:00", "field1": "2022-05-08", "time_diff": "111407.0"},
        id="Time difference between two timestamps with timezone information",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%A, %d. %B %Y %I:%M%p} - ${field1:%Y-%m-%d}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Monday, 05. December 2022 11:19AM", "field1": "2022-12-05"},
        {
            "field2": "Monday, 05. December 2022 11:19AM",
            "field1": "2022-12-05",
            "time_diff": "40740.0",
        },
        id="Time difference between two timestamps with full weekday and month",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%a %b %d %I:%M:%S %p %Y} - ${field1:%Y-%m-%d}",
                "target_field": "time_diff",
            },
        },
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-03"},
        {"field2": "Wed Dec 4 1:14:31 PM 2022", "field1": "2022-12-03", "time_diff": "134071.0"},
        id="Time difference between two timestamps with AM/PM ",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "output_format": "milliseconds",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278000.0",
        },
        id="Time difference between two timestamps with milliseconds output",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "output_format": "nanoseconds",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278000000000.0",
        },
        id="Time difference between two timestamps with nanoseconds output",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05 11:38:42",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "time_diff": "1278.0",
        },
        id="Time difference between two timestamps in subfield",
    ),
    pytest.param(
        {
            "filter": "field1\\. AND some\\.field\\\\2",
            "timestamp_differ": {
                "diff": "${some\\.field\\\\2:%Y-%m-%d %H:%M:%S} - ${field1\\.:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1.": "2022-12-05 11:38:42", "some.field\\2": "2022-12-05 12:00:00"},
        {
            "field1.": "2022-12-05 11:38:42",
            "some.field\\2": "2022-12-05 12:00:00",
            "time_diff": "1278.0",
        },
        id="Time difference between two timestamps in fields with escaping",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 12:00:00", "subfield": {"field2": "2022-12-05T11:38:42-02:00"}},
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42-02:00"},
            "time_diff": "5922.0",
        },
        id="Time difference between two timestamps without specific timestamp format",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "delete_source_fields": True,
            },
        },
        {"field1": "2022-12-05 12:00:00", "subfield": {"field2": "2022-12-05T11:38:42-02:00"}},
        {
            "time_diff": "5922.0",
        },
        id="Time difference between two timestamps with removal of source fields",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "overwrite_target": True,
            },
        },
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42-02:00"},
            "time_diff": "some content",
        },
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42-02:00"},
            "time_diff": "5922.0",
        },
        id="Time difference between two timestamps with overwriting of target",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "merge_with_target": True,
            },
        },
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42-02:00"},
            "time_diff": ["some content"],
        },
        {
            "field1": "2022-12-05 12:00:00",
            "subfield": {"field2": "2022-12-05T11:38:42-02:00"},
            "time_diff": ["some content", "5922.0"],
        },
        id="Time difference between two timestamps with extension of existing list in target field",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": 1670234400, "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": 1670234400,
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "time_diff": "7200.0",
        },
        id="Timestamp diff with integer field (unix epoch)",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 12:00:00.200", "subfield": {"field2": "2022-12-05 12:00:00.500"}},
        {
            "field1": "2022-12-05 12:00:00.200",
            "subfield": {"field2": "2022-12-05 12:00:00.500"},
            "time_diff": "0.3",
        },
        id="Timestamp diff with difference in milliseconds, output in seconds",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
                "output_format": "milliseconds",
            },
        },
        {"field1": "2022-12-05 12:00:00.200", "subfield": {"field2": "2022-12-05 12:00:00.500"}},
        {
            "field1": "2022-12-05 12:00:00.200",
            "subfield": {"field2": "2022-12-05 12:00:00.500"},
            "time_diff": "300.0",
        },
        id="Timestamp diff with difference in milliseconds, output in milliseconds",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2} - ${field1}",
                "target_field": "time_diff",
                "output_format": "nanoseconds",
            },
        },
        {"field1": "2022-12-05 12:00:00.200", "subfield": {"field2": "2022-12-05 12:00:00.500"}},
        {
            "field1": "2022-12-05 12:00:00.200",
            "subfield": {"field2": "2022-12-05 12:00:00.500"},
            "time_diff": "300000000.0",
        },
        id="Timestamp diff with difference in milliseconds, output in nanoseconds",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2} - ${field1}",
                "target_field": "time_diff",
            },
        },
        {"field2": "2022-12-09", "field1": "2022-12-10"},
        {"field2": "2022-12-09", "field1": "2022-12-10", "time_diff": "-86400.0"},
        id="Time difference between two timestamps with negative result",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "output_format": "seconds",
                "show_unit": True,
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": "1278.0 s"},
        id="Time difference between two timestamps with visible second unit",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "output_format": "milliseconds",
                "show_unit": True,
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278000.0 ms",
        },
        id="Time difference between two timestamps with visible millisecond unit",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
                "output_format": "nanoseconds",
                "show_unit": True,
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278000000000.0 ns",
        },
        id="Time difference between two timestamps with visible nanosecond unit",
    ),
]

failure_test_cases = [  # testcase, rule, event, expected, error_message
    pytest.param(
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
        r".*ProcessingWarning.*Invalid isoformat string: 'non-timestamp'",
        id="Timestamp diff with string field",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05", "subfield": {"field2": "2022-12-05 12:00:00"}},
        {
            "field1": "2022-12-05",
            "subfield": {"field2": "2022-12-05 12:00:00"},
            "tags": ["_timestamp_differ_failure"],
        },
        ".*ProcessingWarning.*does not match",
        id="diff between two timestamps with partial timestamp format match",
    ),
    pytest.param(
        {
            "filter": "field1 AND subfield.field2",
            "timestamp_differ": {
                "diff": "${subfield.field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05", "subfield": {"field2": ""}},
        {
            "field1": "2022-12-05",
            "subfield": {"field2": ""},
            "tags": ["_timestamp_differ_failure"],
        },
        r".*ProcessingWarning.*no value for fields: \['subfield.field2'\]",
        id="diff between two timestamps with one empty field",
    ),
    pytest.param(
        {
            "filter": "field1",
            "timestamp_differ": {
                "diff": "${subfield.field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05"},
        {
            "field1": "2022-12-05",
            "tags": ["_timestamp_differ_missing_field_warning"],
        },
        r".*ProcessingWarning.*missing source_fields: \['subfield.field2'\]",
        id="diff between two timestamps with one non existing field",
    ),
    pytest.param(
        {
            "filter": "some_field",
            "timestamp_differ": {
                "diff": "${subfield.field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"some_field": "some value"},
        {
            "some_field": "some value",
            "tags": ["_timestamp_differ_missing_field_warning"],
        },
        r".*ProcessingWarning.*missing source_fields: \['subfield.field2', 'field1']",
        id="diff between two timestamps with non existing fields",
    ),
    pytest.param(
        {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:%Y-%m-%d %H:%M:%S} - ${field1:%Y-%m-%d %H:%M:%S}",
                "target_field": "time_diff",
            },
        },
        {"field1": "2022-12-05 11:38:42", "field2": "2022-12-05 12:00:00", "time_diff": "1278"},
        {
            "field1": "2022-12-05 11:38:42",
            "field2": "2022-12-05 12:00:00",
            "time_diff": "1278",
            "tags": ["_timestamp_differ_failure"],
        },
        ".*FieldExistsWarning.*The following fields could not be written, "
        "because one or more subfields existed and could not be extended: time_diff",
        id="diff between two timestamps with already existing output field",
    ),
]


class TestTimestampDiffer(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "timestamp_differ",
        "rules": ["tests/testdata/unit/timestamp_differ/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event == expected
