# pylint: disable=protected-access
# pylint: disable=missing-docstring
from contextlib import nullcontext as does_not_raise

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
        ["rule", "assert_error_if_expected"],
        [
            pytest.param(
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message"], "target_field": "new_field"},
                },
                does_not_raise(),
                id="decode_with_source_fields",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "decoder": {"source_fields": ["message", "next"], "target_field": "new_field"},
                },
                pytest.raises(ValueError, match=" must be <= 1"),
                id="not_more_than_one_source_field",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "decoder": {"mapping": {"source": "target"}},
                },
                does_not_raise(),
                id="decode_with_mapping",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "decoder": {
                        "mapping": {"source": "target"},
                        "source_format": "not implemented",
                    },
                },
                pytest.raises(
                    ValueError, match="'source_format' must be in.*got 'not implemented'"
                ),
                id="illegal_source_format",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, assert_error_if_expected):
        with assert_error_if_expected:
            rule_instance = DecoderRule.create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("decoder").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @pytest.mark.parametrize(
        ["testcase", "rule1", "rule2", "equality"],
        [
            pytest.param(
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
                id="all_equal",
            ),
            pytest.param(
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
                id="filter_differs",
            ),
            pytest.param(
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
                id="target_differs",
            ),
            pytest.param(
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
                id="source_differs",
            ),
        ],
    )
    def test_equality(self, testcase, rule1, rule2, equality):
        rule1 = DecoderRule.create_from_dict(rule1)
        rule2 = DecoderRule.create_from_dict(rule2)
        assert (rule1 == rule2) == equality, testcase
