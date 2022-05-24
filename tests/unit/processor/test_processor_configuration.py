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
        config = ProcessorConfiguration(normalizer_config)
        assert config.type == "normalizer"
        assert config.hash_salt == "a_secret_tasty_ingredient"
        assert config.generic_rules == ["tests/testdata/unit/normalizer/rules/generic/"]

    def test_raises_on_missing_config_key(self):
        normalizer_config_without_type = {
            "hash_salt": "a_secret_tasty_ingredient",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "regex_mapping": "tests/testdata/unit/normalizer/normalizer_regex_mapping.yml",
            "html_replace_fields": "tests/testdata/unit/normalizer/html_replace_fields.yml",
        }
        with pytest.raises(ProcessorConfigurationError):
            ProcessorConfiguration(normalizer_config_without_type)
