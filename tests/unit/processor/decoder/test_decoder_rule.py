# pylint: disable=protected-access
# pylint: disable=missing-docstring
from contextlib import nullcontext as does_not_raise
from functools import partial

import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.decoder.decoders.registry import DECODERS
from logprep.processor.decoder.decoders.windows_event_log import (
    DATA_SECTIONS,
    DEFAULT_XMLFIELDS,
    XMLFIELD_SECTIONS,
    WindowsEventLogElement,
    XmlFieldSpec,
    parse_xmlfields,
)
from logprep.processor.decoder.rule import DecoderRule


class TestDecoderRule:
    def test_create_from_dict_returns_decoder_rule(self):
        rule = {
            "filter": "message",
            "decoder": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = DecoderRule.create_from_dict(rule)
        assert isinstance(rule_dict, DecoderRule)

    def test_section_constants_match_windows_event_log_enum(self):
        assert set(XMLFIELD_SECTIONS) == {section.value for section in WindowsEventLogElement}
        assert set(DATA_SECTIONS) == set(XMLFIELD_SECTIONS) - {
            WindowsEventLogElement.EVENT.value,
            WindowsEventLogElement.SYSTEM.value,
        }

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

        assert isinstance(rule.xmlfields, tuple)
        assert rule.xmlfields == (
            XmlFieldSpec(
                element="EventID",
                target="EventID",
                section=WindowsEventLogElement.SYSTEM,
                convert=DEFAULT_XMLFIELDS["EventID"].convert,
            ),
            XmlFieldSpec(
                element="Data",
                target="User",
                section=WindowsEventLogElement.EVENT_DATA,
                name="TargetUserName",
                convert=str,
            ),
        )
        assert all(isinstance(spec, XmlFieldSpec) for spec in rule.xmlfields)

    def test_create_from_dict_accepts_xmlfield_specs(self):
        specs = [XmlFieldSpec(target="EventID", convert=str)]
        rule = DecoderRule.create_from_dict(
            {
                "filter": "message",
                "decoder": {
                    "source_format": "windows_event_log",
                    "xmlfields": specs,
                },
            }
        )

        assert rule.xmlfields == (
            XmlFieldSpec(
                element="EventID",
                target="EventID",
                section=WindowsEventLogElement.SYSTEM,
                convert=str,
            ),
        )

    @pytest.mark.parametrize(
        ["xmlfields", "expected_message"],
        [
            pytest.param(
                ["EventID"],
                "must be a dict or a sequence of XmlFieldSpec",
                id="sequence with non-spec item",
            ),
            pytest.param(
                [XmlFieldSpec(target=1, element="EventID")],  # type: ignore
                "non-empty strings",
                id="target not a string",
            ),
            pytest.param(
                [XmlFieldSpec(target="EventID", section="RenderingInfo")],
                "unknown section",
                id="unknown section",
            ),
            pytest.param(
                [XmlFieldSpec(target="Custom", attribute="Name")],
                "'element' is required for new target 'Custom'",
                id="missing element",
            ),
            pytest.param(
                [XmlFieldSpec(target="Custom", element="")],
                "'element' of 'Custom' must be a non-empty string",
                id="empty element",
            ),
            pytest.param(
                [XmlFieldSpec(target="Custom", element=1)],  # type: ignore
                "'element' of 'Custom' must be a string",
                id="element not a string",
            ),
            pytest.param(
                [XmlFieldSpec(target="Custom", element="Data", convert="float")],  # type: ignore
                "'convert' of 'Custom' must be a callable",
                id="convert not callable",
            ),
        ],
    )
    def test_create_from_dict_validates_xmlfield_specs(self, xmlfields, expected_message):
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

        assert parsed == (
            XmlFieldSpec(
                element="EventID",
                target="EventID",
                section=WindowsEventLogElement.SYSTEM,
                convert=DEFAULT_XMLFIELDS["EventID"].convert,
            ),
        )
        assert parse_xmlfields(parsed) == parsed

    def test_decode_func_is_resolved_on_init(self):
        rule = DecoderRule.create_from_dict(
            {
                "filter": "message",
                "decoder": {"source_format": "base64"},
            }
        )

        assert rule.decode_func is DECODERS["base64"]
        assert rule.decode_func("dGhpcyxpcyx0aGUsbWVzc2FnZQ==") == "this,is,the,message"

    def test_decode_func_includes_xmlfields_on_init(self):
        rule = DecoderRule.create_from_dict(
            {
                "filter": "message",
                "decoder": {
                    "source_format": "windows_event_log",
                    "xmlfields": {"EventID": {"convert": "int"}},
                },
            }
        )

        assert isinstance(rule.decode_func, partial)
        assert rule.decode_func.func is DECODERS["windows_event_log"]
        assert rule.decode_func.keywords == {"xmlfields": rule.xmlfields}
