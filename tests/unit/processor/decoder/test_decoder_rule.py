# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest

from logprep.processor.decoder.rule import DecoderRule


class TestDecoderRule:
    def test_create_from_dict_returns_decoder_rule(self):
        rule = {
            "filter": "message",
            "decoder": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = DecoderRule.create_from_dict(rule)
        assert isinstance(rule_dict, DecoderRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message", "next"], "target_field": "new_field"},
                },
                ValueError,
                " must be <= 1",
            ),
            (
                {
                    "filter": "message",
                    "decoder": {"mapping": {"source": "target"}},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "decoder": {
                        "mapping": {"source": "target"},
                        "source_format": "not implemented",
                    },
                },
                ValueError,
                "'source_format' must be in.*got 'not implemented'",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                DecoderRule.create_from_dict(rule)
        else:
            rule_instance = DecoderRule.create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("decoder").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            (
                "equal because equal rules",
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                True,
            ),
            (
                "not equal because different filter",
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "other: message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                False,
            ),
            (
                "not equal because other target",
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "other_field"},
                },
                False,
            ),
            (
                "not equal because other source",
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["other"], "target_field": "new_field"},
                },
                False,
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = DecoderRule.create_from_dict(rule1)
        rule2 = DecoderRule.create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
