# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    ProcessingWarning,
)
from logprep.processor.timestamper.rule import TimestamperRule

test_cases = [
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {
            "source_fields": ["message"],
            "target_field": "new_field",
            "source_format": ["ISO8601"],
            "source_timezone": ZoneInfo("UTC"),
        },
        None,
        None,
        id="use defaults with a source field",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": "UNIX",
                "source_timezone": "Europe/Berlin",
            },
        },
        {
            "source_fields": ["message"],
            "source_format": ["UNIX"],
            "source_timezone": ZoneInfo("Europe/Berlin"),
        },
        None,
        None,
        id="configure source format and timezone",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {},
        },
        {
            "source_fields": [],
            "source_format": None,
            "source_timezone": None,
        },
        None,
        None,
        id="use current time when source fields are omitted",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "target_timezone": "Europe/Berlin",
            },
        },
        {
            "source_fields": [],
            "source_format": None,
            "source_timezone": None,
            "target_timezone": ZoneInfo("Europe/Berlin"),
        },
        None,
        None,
        id="use current time with a target timezone",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message", "timestamp"],
                "target_field": "@timestamp",
            },
        },
        None,
        ValueError,
        r"Length of 'source_fields' must be <= 1",
        id="reject multiple source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_format": "UNIX",
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_format is not allowed when source_fields is omitted or empty",
        id="reject source format without source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_timezone": "Europe/Berlin",
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_timezone is not allowed when source_fields is omitted or empty",
        id="reject source timezone without source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": [],
                "source_format": "UNIX",
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_format is not allowed when source_fields is omitted or empty",
        id="reject source format with empty source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": [],
                "source_timezone": "Europe/Berlin",
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_timezone is not allowed when source_fields is omitted or empty",
        id="reject source timezone with empty source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_format": None,
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_format must not be None when source_fields is configured",
        id="reject source format none with source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "timestamper": {
                "source_fields": ["message"],
                "source_timezone": None,
            },
        },
        None,
        InvalidRuleDefinitionError,
        r"source_timezone must not be None when source_fields is configured",
        id="reject source timezone none with source fields",
    ),
]


parse_datetime_test_cases = [
    pytest.param(
        {
            "source_format": ["ISO8601"],
            "source_timezone": "UTC",
        },
        "2009-06-15 13:45:30Z",
        datetime(2009, 6, 15, 13, 45, 30, tzinfo=UTC),
        None,
        None,
        id="parse ISO8601",
    ),
    pytest.param(
        {
            "source_format": ["UNIX"],
            "source_timezone": "UTC",
        },
        "1700000000",
        datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        None,
        None,
        id="parse UNIX",
    ),
    pytest.param(
        {
            "source_format": ["%Y %m %d - %H:%M:%S"],
            "source_timezone": "Europe/Berlin",
        },
        "2000 12 31 - 22:59:59",
        datetime(
            2000,
            12,
            31,
            22,
            59,
            59,
            tzinfo=ZoneInfo("Europe/Berlin"),
        ),
        None,
        None,
        id="parse custom format with source timezone",
    ),
    pytest.param(
        {
            "source_format": [
                "%Y %m %d",
                "%Y %m %d - %H:%M:%S",
            ],
            "source_timezone": "UTC",
        },
        "2000 12 31 - 22:59:59",
        datetime(2000, 12, 31, 22, 59, 59, tzinfo=UTC),
        None,
        None,
        id="try multiple source formats",
    ),
    pytest.param(
        {
            "source_format": ["UNIX", "%Y-%m-%d"],
            "source_timezone": "UTC",
        },
        "not a timestamp",
        None,
        ProcessingWarning,
        r"Could not parse timestamp",
        id="raise processing warning when no source format matches",
    ),
]


class TestTimestamperRule:
    @pytest.mark.parametrize(
        "rule, expected, error, message",
        test_cases,
    )
    def test_create_from_dict(self, rule, expected, error, message):
        if error:
            with pytest.raises(error, match=message):
                TimestamperRule.create_from_dict(rule)
            return

        rule_instance = TimestamperRule.create_from_dict(rule)

        assert isinstance(rule_instance, TimestamperRule)

        for attribute, value in expected.items():
            assert getattr(rule_instance.config, attribute) == value

    @pytest.mark.parametrize(
        "config, source_value, expected, error, message",
        parse_datetime_test_cases,
    )
    def test_parse_datetime(
        self,
        config,
        source_value,
        expected,
        error,
        message,
    ):
        event = {"message": source_value}
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {
                    "source_fields": ["message"],
                    **config,
                },
            }
        )

        if error:
            with pytest.raises(error, match=message):
                rule.parse_datetime(source_value, event)
            return

        assert rule.parse_datetime(source_value, event) == expected
