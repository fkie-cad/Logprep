# pylint: disable=missing-docstring
import sys
from typing import Optional
from unittest import mock
from attr import define, field, validators
import pytest
from logprep.abc.processor import Processor
from logprep.processor.processor_configuration import (
    ProcessorConfiguration,
    ProcessorConfigurationError,
)


class TestProcessor(Processor):
    @define(kw_only=True)
    class Config(Processor.Config):

        mandatory_attribute: str = field(validator=validators.instance_of(str))
        optional_attribute: Optional[str] = field(
            default=None, validator=validators.optional(validator=validators.instance_of(str))
        )

    def _apply_rules(self, event, rule):
        pass


@mock.patch("os.listdir", return_value=["test_processor"])
@mock.patch("importlib.import_module", return_value=sys.modules[__name__])
class TestProcessorConfiguration:
    def test_reads_test_config(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = ProcessorConfiguration.create(test_config)
        assert config.type == "test_processor"
        assert config.mandatory_attribute == "I am mandatory"
        assert config.generic_rules == ["tests/testdata/unit/normalizer/rules/generic/"]

    def test_raises_on_missing_type(self, _, __):
        test_config = {
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(ProcessorConfigurationError, match=r"'type' not found in configuration"):
            ProcessorConfiguration.create(test_config)

    def test_raises_on_unknown_processor(self, _, __):
        test_config = {
            "type": "unknown_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(
            ProcessorConfigurationError, match=r"processor 'unknown_processor' does not exist"
        ):
            ProcessorConfiguration.create(test_config)

    def test_raises_if_one_mandatory_field_is_missing(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "optional_attribute": "I am optional",
        }
        with pytest.raises(
            TypeError, match=r"missing 1 required .* argument: 'mandatory_attribute'"
        ):
            ProcessorConfiguration.create(test_config)

    def test_raises_if_mandatory_attribute_from_base_is_missing(self, _, __):
        test_config = {
            "type": "test_processor",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "does not matter",
        }
        with pytest.raises(
            TypeError,
            match=r"missing 1 required .* argument: 'specific_rules'",
        ):
            ProcessorConfiguration.create(test_config)

    def test_raises_if_multiple_mandatory_field_are_missing(self, _, __):
        test_config = {
            "type": "test_processor",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
        }
        with pytest.raises(
            TypeError,
            match=r"missing 2 required .* arguments: .*'specific_rules' and 'mandatory_attribute'",
        ):
            ProcessorConfiguration.create(test_config)

    def test_raises_on_wrong_type_in_config_field(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": "tests/testdata/unit/normalizer/rules/specific/",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(TypeError, match=r"'specific_rules' must be <class 'list'>"):
            ProcessorConfiguration.create(test_config)

    def test_raises_on_unknown_field(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
            "i_shoul_not_be_here": "does not matter",
        }
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'i_shoul_not_be_here'"):
            ProcessorConfiguration.create(test_config)

    def test_init_non_mandatory_fields_with_default(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
        }
        config = ProcessorConfiguration.create(test_config)
        assert config.tree_config is None
        assert config.optional_attribute is None

    def test_init_optional_field_in_sub_class(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = ProcessorConfiguration.create(test_config)
        assert config.optional_attribute == "I am optional"

    def test_init_optional_field_in_base_class(self, _, __):
        test_config = {
            "type": "test_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "tree_config": "/tmp",
        }
        config = ProcessorConfiguration.create(test_config)
        assert config.tree_config == "/tmp"
