# pylint: disable=missing-docstring
import re

import pytest

from logprep.processor.field_manager.processor import FieldManager
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "parses iso8601 without pattern",
        {
            "filter": "message",
            "timestamper": {"source_fields": ["message"], "target_field": "@timestamp"},
        },
        {
            "message": "2009-06-15 13:45:30Z",
        },
        {"message": "2009-06-15 13:45:30Z", "@timestamp": "2009-06-15T13:45:30Z"},
    ),
    (
        "parses iso8601 to default target field",
        {
            "filter": "message",
            "timestamper": {"source_fields": ["message"]},
        },
        {
            "message": "2009-06-15 13:45:30Z",
        },
        {"message": "2009-06-15 13:45:30Z", "@timestamp": "2009-06-15T13:45:30Z"},
    ),
    (
        "parses by datetime source format",
        {
            "filter": "message",
            "timestamper": {"source_fields": ["message"], "source_format": "%Y %m %d - %H:%M:%S"},
        },
        {
            "message": "2000 12 31 - 22:59:59",
        },
        {
            "message": "2000 12 31 - 22:59:59",
            "@timestamp": "2000-12-31T22:59:59Z",
        },
    ),
    (
        "converts timezone information",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": "%Y %m %d - %H:%M:%S",
                "source_timezone": "UTC",
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "message": "2000 12 31 - 22:59:59",
        },
        {
            "message": "2000 12 31 - 22:59:59",
            "@timestamp": "2000-12-31T23:59:59+01:00",
        },
    ),
    (
        "parses unix timestamp",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": "UNIX",
                "source_timezone": "UTC",
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "message": "1642160449843",
        },
        {
            "message": "1642160449843",
            "@timestamp": "2022-01-14T12:40:49.843000+01:00",
        },
    ),
    (
        "normalization from timestamp berlin to utc",
        {
            "filter": "winlog.event_id: 123456789",
            "timestamper": {
                "source_fields": ["winlog.event_data.some_timestamp_berlin"],
                "target_field": "@timestamp",
                "source_format": "%Y %m %d - %H:%M:%S",
                "source_timezone": "Europe/Berlin",
                "target_timezone": "UTC",
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_berlin": "1999 12 12 - 12:12:22"},
            }
        },
        {
            "@timestamp": "1999-12-12T11:12:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_berlin": "1999 12 12 - 12:12:22"},
            },
        },
    ),
    (
        "normalization from timestamp same timezone",
        {
            "filter": "winlog.event_id: 123456789",
            "timestamper": {
                "source_fields": ["winlog.event_data.some_timestamp_utc"],
                "target_field": "@timestamp",
                "source_format": "%Y %m %d - %H:%M:%S",
                "source_timezone": "UTC",
                "target_timezone": "UTC",
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            }
        },
        {
            "@timestamp": "1999-12-12T12:12:22Z",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22"},
            },
        },
    ),
    (
        "normalization from unix with millis timestamp",
        {
            "filter": "winlog.event_id: 123456789",
            "timestamper": {
                "source_fields": ["winlog.event_data.some_timestamp_utc"],
                "target_field": "@timestamp",
                "source_format": "UNIX",
                "source_timezone": "UTC",
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449843"},
            }
        },
        {
            "@timestamp": "2022-01-14T12:40:49.843000+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449843"},
            },
        },
    ),
    (
        "normalization from unix with seconds timestamp",
        {
            "filter": "winlog.event_id: 123456789",
            "timestamper": {
                "source_fields": ["winlog.event_data.some_timestamp_utc"],
                "target_field": "@timestamp",
                "source_format": "UNIX",
                "source_timezone": "UTC",
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            }
        },
        {
            "@timestamp": "2022-01-14T12:40:49+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            },
        },
    ),
    (
        "attempt parsing with multiple patterns, second one successful",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": ["%Y %m %d", "%Y %m %d - %H:%M:%S"],
            },
        },
        {
            "message": "2000 12 31 - 22:59:59",
        },
        {
            "message": "2000 12 31 - 22:59:59",
            "@timestamp": "2000-12-31T22:59:59Z",
        },
    ),
    (
        "attempt parsing with multiple patterns, both successful but stopping after first",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": ["%Y %m %d - %H:%M:%S", "%Y %m %d - %H:%M:%S"],
            },
        },
        {
            "message": "2000 12 31 - 22:59:59",
        },
        {
            "message": "2000 12 31 - 22:59:59",
            "@timestamp": "2000-12-31T22:59:59Z",
        },
    ),
]

failure_test_cases = [
    (
        "normalization from timestamp with non matching patterns",
        {
            "filter": "winlog.event_id: 123456789",
            "timestamper": {
                "source_fields": ["winlog.event_data.some_timestamp_utc"],
                "target_field": "@timestamp",
                "source_format": ["a%Y %m"],
                "source_timezone": "UTC",
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22 UTC"},
            }
        },
        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1999 12 12 - 12:12:22 UTC"},
            },
            "tags": ["_timestamper_failure"],
        },
        r"Could not parse timestamp",
    ),
    (
        "attempt parsing with multiple patterns, none is successful",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": ["%Y %m %d", "%H:%M:%S"],
            },
        },
        {
            "message": "2000 12 31 - 22:59:59",
        },
        {"message": "2000 12 31 - 22:59:59", "tags": ["_timestamper_failure"]},
        r"Could not parse timestamp",
    ),
    (
        "attempt parsing valid ISO8601 with not matching pattern",
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": ["%Y-%m-%dT%H:%M:%S"],
            },
        },
        {
            "message": "2019-09-07T15:50",
        },
        {"message": "2019-09-07T15:50", "tags": ["_timestamper_failure"]},
        r"Could not parse timestamp",
    ),
    (
        "raises if source field is none",
        {"filter": "message", "timestamper": {"source_fields": ["@timestamp"]}},
        {"message": "this does not matter"},
        {"message": "this does not matter", "tags": ["_timestamper_missing_field_warning"]},
        r"missing source_fields: \['@timestamp']",
    ),
]  # testcase, rule, event, expected


class TestTimestamper(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "timestamper",
        "rules": ["tests/testdata/unit/timestamper/rules"],
    }

    def test_is_field_manager_implementation(self):
        assert isinstance(self.object, FieldManager)
        assert issubclass(self.object.rule_class, FieldManager.rule_class)

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
        assert event == expected, testcase
