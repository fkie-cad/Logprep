# pylint: disable=protected-access
# pylint: disable=missing-docstring

from zoneinfo import ZoneInfo

import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
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
