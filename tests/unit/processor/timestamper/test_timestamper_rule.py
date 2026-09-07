# pylint: disable=protected-access
# pylint: disable=missing-docstring

import pytest

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
                        "source_fields": ["message", "timestamp"],
                        "target_field": "@timestamp",
                    },
                },
                ValueError,
                r"Length of 'source_fields' must be <= 1",
                id="multiple source fields",
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
                assert value == getattr(rule_instance._config, key)
