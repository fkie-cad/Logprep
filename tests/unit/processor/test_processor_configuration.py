# pylint: disable=missing-docstring
import pytest
from logprep.processor.processor_configuration import (
    ProcessorConfiguration,
    ProcessorConfigurationError,
)


class TestProcessorConfiguration:
    def test_reads_normalizer_config(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        config = ProcessorConfiguration.create(normalizer_config)
        assert config.type == "normalizer"
        assert config.hash_salt == "a_secret_tasty_ingredient"
        assert config.generic_rules == ["tests/testdata/unit/normalizer/rules/generic/"]

    def test_raises_on_missing_type(self):
        normalizer_config_without_type = {
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        with pytest.raises(ProcessorConfigurationError, match=r"'type' not found in configuration"):
            ProcessorConfiguration.create(normalizer_config_without_type)

    def test_raises_on_unknown_processor(self):
        normalizer_config_without_type = {
            "type": "unknown_processor",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        with pytest.raises(
            ProcessorConfigurationError, match=r"processor 'unknown_processor' does not exist"
        ):
            ProcessorConfiguration.create(normalizer_config_without_type)

    def test_raises_if_one_mandatory_field_is_missing(self):
        normalizer_config_without_type = {
            "type": "normalizer",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        with pytest.raises(TypeError, match=r"missing 1 required .* argument: 'hash_salt'"):
            ProcessorConfiguration.create(normalizer_config_without_type)

    def test_raises_if_multiple_mandatory_field_are_missing(self):
        normalizer_config_without_type = {
            "type": "normalizer",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
        }
        with pytest.raises(
            TypeError,
            match=r"missing 2 required .* arguments: 'hash_salt' and 'html_replace_fields'",
        ):
            ProcessorConfiguration.create(normalizer_config_without_type)

    def test_raises_on_wrong_type_in_config_field(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": "tests/testdata/unit/normalizer/rules/specific/",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        with pytest.raises(TypeError, match=r"'specific_rules' must be <class 'list'>"):
            ProcessorConfiguration.create(normalizer_config)

    def test_raises_on_unknown_field(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
            "i_shoul_not_be_here": "does not matter",
        }
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'i_shoul_not_be_here'"):
            ProcessorConfiguration.create(normalizer_config)

    def test_init_non_mandatory_fields_with_default(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        config = ProcessorConfiguration.create(normalizer_config)
        assert config.tree_config is None
        assert config.count_grok_pattern_matches is None

    def test_init_optional_field_in_sub_class(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
            "count_grok_pattern_matches": {"count_directory_path": "/tmp", "write_period": 0},
        }
        config = ProcessorConfiguration.create(normalizer_config)
        assert config.count_grok_pattern_matches == {
            "count_directory_path": "/tmp",
            "write_period": 0,
        }

    def test_init_optional_field_in_base_class(self):
        normalizer_config = {
            "type": "normalizer",
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
            "tree_config": "/tmp",
        }
        config = ProcessorConfiguration.create(normalizer_config)
        assert config.type == "normalizer"
