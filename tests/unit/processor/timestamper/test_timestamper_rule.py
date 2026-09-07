# pylint: disable=protected-access
# pylint: disable=missing-docstring

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    ProcessingWarning,
)
from logprep.processor.timestamper.rule import TimestamperRule


class TestTimestamperRule:
    def test_create_from_dict_returns_timestamper_rule(self):
        rule = {
            "filter": "message",
            "timestamper": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = TimestamperRule.create_from_dict(rule)
        assert isinstance(rule_dict, TimestamperRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": ["message"],
                        "target_field": "@timestamp",
                    },
                },
                None,
                None,
                id="source field",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": ["message"],
                        "target_field": "@timestamp",
                        "source_format": ["UNIX"],
                    },
                },
                None,
                None,
                id="source format with source field",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": ["message"],
                        "source_timezone": "Europe/Berlin",
                    },
                },
                None,
                None,
                id="source timezone with source field",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {},
                },
                None,
                None,
                id="current time without source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": [],
                    },
                },
                None,
                None,
                id="current time with empty source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": ["message", "timestamp"],
                        "target_field": "@timestamp",
                    },
                },
                ValueError,
                r"Length of 'source_fields' must be <= 1",
                id="multiple source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_format": "UNIX",
                    },
                },
                InvalidRuleDefinitionError,
                r"source_format is not allowed when source_fields is omitted or empty",
                id="source format without source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_timezone": "Europe/Berlin",
                    },
                },
                InvalidRuleDefinitionError,
                r"source_timezone is not allowed when source_fields is omitted or empty",
                id="source timezone without source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": [],
                        "source_format": "UNIX",
                    },
                },
                InvalidRuleDefinitionError,
                r"source_format is not allowed when source_fields is omitted or empty",
                id="source format with empty source fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "timestamper": {
                        "source_fields": [],
                        "source_timezone": "Europe/Berlin",
                    },
                },
                InvalidRuleDefinitionError,
                r"source_timezone is not allowed when source_fields is omitted or empty",
                id="source timezone with empty source fields",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                TimestamperRule.create_from_dict(rule)
        else:
            rule_instance = TimestamperRule.create_from_dict(rule)
            assert hasattr(rule_instance, "_config")

            for key, value in rule.get("timestamper").items():
                assert hasattr(rule_instance._config, key)

                config_value = getattr(rule_instance._config, key)

                if key == "source_timezone":
                    assert config_value == ZoneInfo(value)
                else:
                    assert value == config_value

    def test_source_defaults_when_source_fields_are_configured(self):
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {
                    "source_fields": ["message"],
                },
            }
        )

        assert rule.source_format == ["ISO8601"]
        assert rule.source_timezone == ZoneInfo("UTC")

    def test_source_defaults_when_source_fields_are_omitted(self):
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {},
            }
        )

        assert rule.source_format is None
        assert rule.source_timezone is None

    def test_source_defaults_when_source_fields_are_empty(self):
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {
                    "source_fields": [],
                },
            }
        )

        assert rule.source_format is None
        assert rule.source_timezone is None

    @pytest.mark.parametrize(
        "source_value, source_format, source_timezone, expected",
        [
            pytest.param(
                "2009-06-15 13:45:30Z",
                ["ISO8601"],
                "UTC",
                datetime(2009, 6, 15, 13, 45, 30, tzinfo=UTC),
                id="iso8601",
            ),
            pytest.param(
                "1700000000",
                ["UNIX"],
                "UTC",
                datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
                id="unix",
            ),
            pytest.param(
                "2000 12 31 - 22:59:59",
                ["%Y %m %d - %H:%M:%S"],
                "Europe/Berlin",
                datetime(
                    2000,
                    12,
                    31,
                    22,
                    59,
                    59,
                    tzinfo=ZoneInfo("Europe/Berlin"),
                ),
                id="custom format with source timezone",
            ),
            pytest.param(
                "2000 12 31 - 22:59:59",
                ["%Y %m %d", "%Y %m %d - %H:%M:%S"],
                "UTC",
                datetime(2000, 12, 31, 22, 59, 59, tzinfo=UTC),
                id="uses matching source format",
            ),
        ],
    )
    def test_parse_datetime(
        self,
        source_value,
        source_format,
        source_timezone,
        expected,
    ):
        event = {"message": source_value}
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {
                    "source_fields": ["message"],
                    "source_format": source_format,
                    "source_timezone": source_timezone,
                },
            }
        )

        result = rule.parse_datetime(source_value, event)

        assert result == expected

    def test_parse_datetime_raises_processing_warning_if_no_format_matches(self):
        event = {"message": "not a timestamp"}
        rule = TimestamperRule.create_from_dict(
            {
                "filter": "message",
                "timestamper": {
                    "source_fields": ["message"],
                    "source_format": ["UNIX", "%Y-%m-%d"],
                },
            }
        )

        with pytest.raises(ProcessingWarning, match=r"Could not parse timestamp"):
            rule.parse_datetime(event["message"], event)
