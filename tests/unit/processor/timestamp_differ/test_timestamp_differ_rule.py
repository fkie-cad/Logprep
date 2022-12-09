# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.timestamp_differ.rule import TimestampDifferRule


class TestTimestampDifferRule:
    def test_returns_rule(self):
        rule_dict = {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        }
        rule = TimestampDifferRule._create_from_dict(rule_dict)
        assert rule

    def test_diff_field_is_split_in_fields_and_formats(self):
        rule_dict = {
            "filter": "field1 AND field2",
            "timestamp_differ": {
                "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                "target_field": "time_diff",
            },
        }
        rule = TimestampDifferRule._create_from_dict(rule_dict)
        assert rule.source_fields == ["field2", "field1"]
        assert rule.source_field_formats == ["YYYY-MM-DD HH:mm:ss", "YYYY-MM-DD HH:mm:ss"]

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "field1 AND subfield.field2",
                    "timestamp_differ": {
                        "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                        "target_field": "time_diff",
                    },
                },
                ValueError,
                "'diff' must match regex",
            ),
            (
                {
                    "filter": "field1 AND subfield.field2",
                    "timestamp_differ": {
                        "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                        "target_field": "time_diff",
                    },
                },
                ValueError,
                "'diff' must match regex",
            ),
            (
                {
                    "filter": "field1 AND subfield.field2",
                    "timestamp_differ": {
                        "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} + ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                        "target_field": "time_diff",
                    },
                },
                ValueError,
                "'diff' must match regex",
            ),
            (
                {
                    "filter": "field1 AND subfield.field2",
                    "timestamp_differ": {
                        "diff": "${subfield.field2:YYYY-MM-DD HH:mm:ss} something ${subfield.field2:YYYY-MM-DD HH:mm:ss}",
                        "target_field": "time_diff",
                    },
                },
                ValueError,
                "'diff' must match regex",
            ),
            (
                {
                    "filter": "field1 AND subfield.field2",
                    "timestamp_differ": {
                        "diff": "some ${subfield.field2:YYYY-MM-DD HH:mm:ss} - ${subfield.field2:YYYY-MM-DD HH:mm:ss} thing",
                        "target_field": "time_diff",
                    },
                },
                ValueError,
                "'diff' must match regex",
            ),
            (
                {
                    "filter": "field1 AND field2",
                    "timestamp_differ": {
                        "diff": "${field2:YYYY-MM-DD HH:mm:ss} - ${field1:YYYY-MM-DD HH:mm:ss}",
                        "target_field": "time_diff",
                    },
                },
                None,
                None,
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                TimestampDifferRule._create_from_dict(rule)
        else:
            rule_instance = TimestampDifferRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("timestamp_differ").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)
