# pylint: disable=missing-docstring
from copy import deepcopy
import sys
from typing import Optional
from unittest import mock

import pytest
from attr import define, field, validators
from logprep.abc.processor import Processor
from logprep.processor.processor_configuration import ProcessorConfiguration
from logprep.processor.processor_factory_error import (
    NoTypeSpecifiedError,
    UnknownProcessorTypeError,
)
from logprep.processor.processor_registry import ProcessorRegistry


class MockProcessor(Processor):
    @define(kw_only=True)
    class Config(Processor.Config):

        mandatory_attribute: str = field(validator=validators.instance_of(str))
        optional_attribute: Optional[str] = field(
            default=None, validator=validators.optional(validator=validators.instance_of(str))
        )

    def _apply_rules(self, event, rule):
        pass


original_registry_mapping = deepcopy(ProcessorRegistry.mapping)


class TestProcessorConfiguration:
    def setup_method(self):
        ProcessorRegistry.mapping = {"mock_processor": MockProcessor}

    def teardown_method(self):
        ProcessorRegistry.mapping = original_registry_mapping

    def test_reads_test_config(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = ProcessorConfiguration.create("dummy name", test_config)
        assert config.type == "mock_processor"
        assert config.mandatory_attribute == "I am mandatory"
        assert config.generic_rules == ["tests/testdata/unit/normalizer/rules/generic/"]

    def test_raises_on_missing_type(self):
        test_config = {
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(NoTypeSpecifiedError):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_on_unknown_processor(self):
        test_config = {
            "type": "unknown_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(UnknownProcessorTypeError):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_if_one_mandatory_field_is_missing(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "optional_attribute": "I am optional",
        }
        with pytest.raises(
            TypeError, match=r"missing 1 required .* argument: 'mandatory_attribute'"
        ):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_if_mandatory_attribute_from_base_is_missing(self):
        test_config = {
            "type": "mock_processor",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "does not matter",
        }
        with pytest.raises(
            TypeError,
            match=r"missing 1 required .* argument: 'specific_rules'",
        ):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_if_multiple_mandatory_field_are_missing(self):
        test_config = {
            "type": "mock_processor",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
        }
        with pytest.raises(
            TypeError,
            match=r"missing 2 required .* arguments: .*'specific_rules' and 'mandatory_attribute'",
        ):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_on_wrong_type_in_config_field(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": "tests/testdata/unit/normalizer/rules/specific/",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(TypeError, match=r"'specific_rules' must be <class 'list'>"):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_raises_on_unknown_field(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
            "i_shoul_not_be_here": "does not matter",
        }
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'i_shoul_not_be_here'"):
            ProcessorConfiguration.create("dummy name", test_config)

    def test_init_non_mandatory_fields_with_default(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
        }
        config = ProcessorConfiguration.create("dummy name", test_config)
        assert config.tree_config is None
        assert config.optional_attribute is None

    def test_init_optional_field_in_sub_class(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = ProcessorConfiguration.create("dummy name", test_config)
        assert config.optional_attribute == "I am optional"

    def test_init_optional_field_in_base_class(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "tree_config": "/tmp",
        }
        config = ProcessorConfiguration.create("dummy name", test_config)
        assert config.tree_config == "/tmp"
