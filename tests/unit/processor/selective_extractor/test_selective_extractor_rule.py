# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use

from typing import Hashable
from unittest import mock

import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.selective_extractor.rule import (
    SelectiveExtractorRule,
    SelectiveExtractorRuleError,
)


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "test",
        "selective_extractor": {
            "source_fields": ["field1", "field2"],
            "outputs": [{"kafka": "topic"}],
        },
        "description": "my reference rule",
    }
@pytest.fixture(name="template_rule_definition")
def fixture_template_rule_definition():
    return {
        "filter": "test",
        "selective_extractor": {
            "event_template": {"field1": "${field1}", "field2": "${field2}"},
            "outputs": [{"kafka": "topic"}],
        },
        "description": "my reference rule",
    }

class TestSelectiveExtractorRule:
    @mock.patch("pathlib.Path.is_file", return_value=True)
    def test_rule_has_fields_from_file_path(self, _):
        rule_definition = {
            "filter": "test",
            "selective_extractor": {
                "extract_from_file": "my/file",
                "outputs": [{"kafka": "topic"}],
            },
        }
        read_lines = b"test1\r\ntest2"
        with mock.patch("pathlib.Path.read_bytes", return_value=read_lines):
            rule = SelectiveExtractorRule.create_from_dict(rule_definition)
            extracted_field_list = rule.extracted_field_list
            assert rule._config.extract_from_file == "my/file"
            assert "test1" in extracted_field_list
            assert "test2" in extracted_field_list

    @mock.patch("pathlib.Path.is_file", return_value=False)
    def test_rule_has_fields_from_directory_path(self, _):
        rule_definition = {
            "filter": "test",
            "selective_extractor": {
                "extract_from_file": "my/path/",
                "outputs": [{"kafka": "topic"}],
            },
        }
        with pytest.raises(SelectiveExtractorRuleError):
            _ = SelectiveExtractorRule.create_from_dict(rule_definition)

    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of one list element is missing",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other topic",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "outputs": [{"kafka": "other"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other output",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "outputs": [{"opensearch": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other output and other topic",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "outputs": [{"opensearch": "_other"}],
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract_from_file": "field1\r\nfield2",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                True,
            ),
            (
                "Should not be equal cause file value results in different extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract_from_file": "field1\r\nfield2\r\nfield3",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should not be equal cause file value results in different extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1", "field2"],
                        "extract_from_file": "field1\r\nfield2\r\nfield3",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "extract_from_file": "field1\r\nfield2",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                True,
            ),
            (
                "Should not be equal cause one rule uses a template",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"value": "${field1}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            read_lines = other_rule_definition.get("selective_extractor").get("extract_from_file")
            if read_lines is not None:
                read_lines = read_lines.encode("utf8")

            with mock.patch("pathlib.Path.read_bytes", return_value=read_lines):
                rule1 = SelectiveExtractorRule.create_from_dict(rule_definition)
                rule2 = SelectiveExtractorRule.create_from_dict(other_rule_definition)
                assert (rule1 == rule2) == is_equal, testcase
    # Same equality test as above for template feature
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of one template element is missing",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of different template value",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${other_field}", "field2": "${field2}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other topic",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                        "outputs": [{"kafka": "other"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other output",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                        "outputs": [{"opensearch": "topic"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other output and other topic",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                        "outputs": [{"opensearch": "_other"}],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause outputs are missing",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}", "field2": "${field2}"},
                    },
                },
                False,
            ),
            (
            "Should not be equal cause string conversion of different fields",
            {
                "filter": "test",
                "selective_extractor": {
                    "event_template": {"field1": "${field1|str}", "field2": "${field2}"},
                    "outputs": [{"kafka": "topic"}],
                },
            },
            False,
        ),
        ],
    )
    def test_template_rules_equality(
        self,
        template_rule_definition,
        testcase,
        other_rule_definition,
        is_equal,
    ):
        rule1 = SelectiveExtractorRule.create_from_dict(template_rule_definition)
        rule2 = SelectiveExtractorRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
    @pytest.mark.parametrize(
        "rule_definition, read_lines, raised, message",
        [
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract_from_file": "my/path/",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "no field to extract",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract_from_file": "my/path/",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"field1",
                None,
                None,
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "extract_from_file": "my/path/",
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                None,
                None,
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "extract_from_file": "my/path/",
                    },
                },
                b"",
                TypeError, # with optional output None,
                "missing 1 required keyword-only argument: 'outputs'", # with optional output None,
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "outputs": [{"kafka": "topic1"}, {"opensearch": "_target"}],
                    },
                },
                b"",
                None,
                None,
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "outputs": [{"kafka": "topic1"}],
                        "target_field": "bla",
                    },
                },
                b"",
                TypeError,
                "got an unexpected keyword argument 'target_field'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "outputs": [{"kafka": "topic"}],
                        "overwrite_target": False,
                    },
                },
                b"",
                TypeError,
                "got an unexpected keyword argument 'overwrite_target'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "outputs": [{"kafka": "topic"}],
                        "merge_with_target": True,
                    },
                },
                b"",
                TypeError,
                "got an unexpected keyword argument 'merge_with_target'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}","field2": "${field2}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                None,
                None,
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"field1": "${field1}","field2": "${field2}"},
                    },
                },
                b"",
                None, # If output stays non optional TypeError,
                None,# If output stays non optional "missing 1 required keyword-only argument: 'outputs'"
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "source_fields": ["field1"],
                        "event_template": {"field1": "${field1}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "event_template cannot be combined with source_fields or extract_from_file",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract_from_file": "my/path/",
                        "event_template": {"field1": "${field1}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"field1",
                InvalidRuleDefinitionError,
                "event_template cannot be combined with source_fields or extract_from_file",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "event_template must not be empty",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": ["${field1}", "${field2}"],
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "event_template must be a mapping",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {"value": "${field1|unknown}"},
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "types can only be converted to strings",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                InvalidRuleDefinitionError,
                "no field to extract",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "event_template": {
                            "content": {
                                "value": "${raw_value|str}",
                                "ttl": "${ttl}",
                            }
                        },
                        "outputs": [{"kafka": "topic"}],
                    },
                },
                b"",
                None,
                None,
        ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, read_lines, raised, message):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            with mock.patch("pathlib.Path.read_bytes", return_value=read_lines):
                if raised:
                    with pytest.raises(raised, match=message):
                        _ = SelectiveExtractorRule.create_from_dict(rule_definition)
                else:
                    extractor_rule = SelectiveExtractorRule.create_from_dict(rule_definition)
                    assert isinstance(extractor_rule, SelectiveExtractorRule)

    def test_rule_is_hashable(self, rule_definition):
        rule = SelectiveExtractorRule.create_from_dict(rule_definition)
        assert isinstance(rule, Hashable)
