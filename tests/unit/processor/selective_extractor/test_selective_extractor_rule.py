# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use

from pathlib import Path
from typing import Hashable
from unittest import mock
import pytest

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.factory_error import InvalidConfigurationError
from logprep.processor.selective_extractor.rule import (
    SelectiveExtractorRule,
    SelectiveExtractorRuleError,
)


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "test",
        "selective_extractor": {
            "extract": {
                "extracted_field_list": ["field1", "field2"],
                "target_topic": "topic1",
            },
        },
        "description": "my reference rule",
    }


class TestSelectiveExtractorRule:
    def test_rule_has_extract_fields(self, specific_rule_definition):
        rule = SelectiveExtractorRule._create_from_dict(specific_rule_definition)
        extracted_field_list = rule._config.extract.get("extracted_field_list")
        assert isinstance(extracted_field_list, list)
        assert "field1" in extracted_field_list

    def test_rule_has_target_topic(self, specific_rule_definition):
        rule = SelectiveExtractorRule._create_from_dict(specific_rule_definition)
        assert rule.target_topic is not None
        assert rule.target_topic == "topic1"

    @mock.patch("pathlib.Path.is_file", return_value=True)
    def test_rule_has_fields_from_file_path(self, _):
        rule_definition = {
            "filter": "test",
            "selective_extractor": {
                "extract": {
                    "extract_from_file": "my/file",
                    "target_topic": "topic1",
                },
            },
        }
        read_lines = "test1\r\ntest2"
        with mock.patch("pathlib.Path.read_text", return_value=read_lines):
            rule = SelectiveExtractorRule._create_from_dict(rule_definition)
            extracted_field_list = rule.extracted_field_list
            assert rule._config.extract_from_file == Path("my/file")
            assert "test1" in extracted_field_list
            assert "test2" in extracted_field_list

    @mock.patch("pathlib.Path.is_file", return_value=False)
    def test_rule_has_fields_from_directory_path(self, _):
        rule_definition = {
            "filter": "test",
            "selective_extractor": {
                "extract": {
                    "extract_from_file": "my/path/",
                    "target_topic": "topic1",
                },
            },
        }
        with pytest.raises(SelectiveExtractorRuleError):
            _ = SelectiveExtractorRule._create_from_dict(rule_definition)

    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "target_topic": "topic1",
                        },
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "target_topic": "topic1",
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of one list element is missing",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1"],
                            "target_topic": "topic1",
                        },
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other topic",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "target_topic": "other_topic",
                        },
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extract_from_file": "field1\r\nfield2",
                            "target_topic": "topic1",
                        },
                    },
                },
                True,
            ),
            (
                "Should not be equal cause file value results in different extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extract_from_file": "field1\r\nfield2\r\nfield3",
                            "target_topic": "topic1",
                        },
                    },
                },
                False,
            ),
            (
                "Should not be equal cause file value results in different extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "extract_from_file": "field1\r\nfield2\r\nfield3",
                            "target_topic": "topic1",
                        },
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same extracted values",
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1"],
                            "extract_from_file": "field1\r\nfield2",
                            "target_topic": "topic1",
                        },
                    },
                },
                True,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            read_lines = (
                other_rule_definition.get("selective_extractor")
                .get("extract")
                .get("extract_from_file")
            )

            with mock.patch("pathlib.Path.read_text", return_value=read_lines):
                rule1 = SelectiveExtractorRule._create_from_dict(specific_rule_definition)
                rule2 = SelectiveExtractorRule._create_from_dict(other_rule_definition)
                assert (rule1 == rule2) == is_equal, testcase

    @pytest.mark.parametrize(
        "rule_definition, raised, message",
        [
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extract_from_file": "my/path/",
                            "target_topic": "topic1",
                        },
                    },
                },
                None,
                "extract_from_file and target topic",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {},
                },
                TypeError,
                "missing 1 required keyword-only argument: 'extract'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": "field1, field2",
                },
                InvalidRuleDefinitionError,
                "config is not a dict",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {"extract": "field1"},
                },
                TypeError,
                "'extract' must be <class 'dict'>",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {},
                    },
                },
                ValueError,
                r"extract has to contain one of these members \['extracted_field_list', 'extract_from_file'\]",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {"extracted_field_list": "field1", "target_topic": "test_topic"},
                    },
                },
                InvalidConfigurationError,
                "'extracted_field_list' has wrong type",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extract_from_file": ["file1", "file2"],
                            "target_topic": "test_topic",
                        },
                    },
                },
                InvalidConfigurationError,
                "'extract_from_file' has wrong type",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "target_topic": "topic1",
                        },
                    },
                    "description": "my reference rule",
                },
                None,
                "extracted field list with target topic",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {"extracted_field_list": ["field1", "field2"]},
                    },
                    "description": "rule with list and without target_topic should raise",
                },
                InvalidConfigurationError,
                "following key is missing: 'target_topic'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extracted_field_list": ["field1", "field2"],
                            "target_topic": ["topic1", "topic2"],
                        },
                    },
                    "description": "rule with list and without target_topic should raise",
                },
                InvalidConfigurationError,
                "'target_topic' has wrong type",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {"extract_from_file": "mockfile"},
                    },
                    "description": "rule with list and without target_topic should raise",
                },
                InvalidConfigurationError,
                "following key is missing: 'target_topic'",
            ),
            (
                {
                    "filter": "test",
                    "selective_extractor": {
                        "extract": {
                            "extract_from_file": "mockfile",
                            "target_topic": ["topic1", "topic2"],
                        },
                    },
                    "description": "rule with list and without target_topic should raise",
                },
                InvalidConfigurationError,
                "'target_topic' has wrong type",
            ),
        ],
    )
    def test_rule_create_from_dict(self, rule_definition, raised, message):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            if raised:
                with pytest.raises(raised, match=message):
                    _ = SelectiveExtractorRule._create_from_dict(rule_definition)
            else:
                with mock.patch("pathlib.Path.read_text", return_value=""):
                    extractor_rule = SelectiveExtractorRule._create_from_dict(rule_definition)
                    assert isinstance(extractor_rule, SelectiveExtractorRule)

    def test_rule_is_hashable(self, specific_rule_definition):
        rule = SelectiveExtractorRule._create_from_dict(specific_rule_definition)
        assert isinstance(rule, Hashable)
