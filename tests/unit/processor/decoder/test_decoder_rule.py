# pylint: disable=protected-access
# pylint: disable=missing-docstring
from contextlib import nullcontext as does_not_raise

import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.decoder.decoders.windows_event_log import (
    DEFAULT_XML_FIELDS,
    XmlFieldSpec,
)
from logprep.processor.decoder.rule import (
    DecoderRule,
    XmlFieldOverrides,
    parse_xmlfields,
)


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

    def test_create_from_dict_resolves_xmlfields_to_field_specs(self):
        raw_xmlfields = {
            "EventID": {"convert": "int"},
            "User": {"element": "Data", "section": "EventData", "name": "TargetUserName"},
        }
        rule = DecoderRule.create_from_dict(
            {
                "filter": "message",
                "decoder": {
                    "source_format": "windows_event_log",
                    "xmlfields": raw_xmlfields,
                },
            }
        )

        assert rule.xmlfields == {
            "EventID": XmlFieldSpec(
                element="EventID",
                target="EventID",
                convert=DEFAULT_XML_FIELDS["EventID"].convert,
            ),
            "User": XmlFieldSpec(
                element="Data", target="User", section="EventData", name="TargetUserName"
            ),
        }
        assert all(isinstance(value, XmlFieldSpec) for value in rule.xmlfields.values())

    def test_create_from_dict_accepts_xmlfield_overrides_instances(self):
        overrides = XmlFieldOverrides(element="EventID", convert="str")
        rule = DecoderRule.create_from_dict(
            {
                "filter": "message",
                "decoder": {
                    "source_format": "windows_event_log",
                    "xmlfields": {"EventID": overrides},
                },
            }
        )

        assert rule.xmlfields == {
            "EventID": XmlFieldSpec(element="EventID", target="EventID", convert=str)
        }
        assert isinstance(rule.xmlfields["EventID"], XmlFieldSpec)

    @pytest.mark.parametrize(
        ["xmlfields", "expected_message"],
        [
            pytest.param(
                {"EventID": XmlFieldOverrides(convert="float")},  # type: ignore
                "unknown convert type",
                id="unknown convert type in overrides instance",
            ),
            pytest.param(
                {"EventID": XmlFieldOverrides(section="RenderingInfo")},
                "unknown section",
                id="unknown section in overrides instance",
            ),
            pytest.param(
                {"Custom": XmlFieldOverrides(attribute="Name")},
                "'element' is required for new target 'Custom'",
                id="missing element in overrides instance",
            ),
            pytest.param(
                {"Custom": XmlFieldOverrides(element="")},
                "'element' of 'Custom' must be a non-empty string",
                id="empty element in overrides instance",
            ),
            pytest.param(
                {"EventID": XmlFieldOverrides(convert=1)},  # type: ignore
                "'convert' of 'EventID' must be a string",
                id="wrong type in overrides instance",
            ),
        ],
    )
    def test_create_from_dict_validates_xmlfield_overrides_instances(
        self, xmlfields, expected_message
    ):
        with pytest.raises(InvalidRuleDefinitionError, match=expected_message):
            DecoderRule.create_from_dict(
                {
                    "filter": "message",
                    "decoder": {
                        "source_format": "windows_event_log",
                        "xmlfields": xmlfields,
                    },
                }
            )

    def test_parse_xmlfields_is_idempotent(self):
        parsed = parse_xmlfields({"EventID": {"convert": "int"}})

        assert parsed == {
            "EventID": XmlFieldSpec(
                element="EventID",
                target="EventID",
                convert=DEFAULT_XML_FIELDS["EventID"].convert,
            )
        }
        assert parse_xmlfields(parsed) == parsed
