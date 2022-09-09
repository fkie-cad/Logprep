# pylint: disable=missing-docstring
from copy import deepcopy
from typing import Optional

import pytest
from attr import define, field, validators
from logprep.abc.processor import Processor
from logprep.configuration import Configuration
from logprep.factory_error import (
    NoTypeSpecifiedError,
    UnknownComponentTypeError,
)
from logprep.registry import Registry


class MockProcessor(Processor):
    @define(kw_only=True)
    class Config(Processor.Config):

        mandatory_attribute: str = field(validator=validators.instance_of(str))
        optional_attribute: Optional[str] = field(
            default=None, validator=validators.optional(validator=validators.instance_of(str))
        )

    def _apply_rules(self, event, rule):
        pass


original_registry_mapping = deepcopy(Registry.mapping)


class TestConfiguration:
    def setup_method(self):
        Registry.mapping = {"mock_processor": MockProcessor}

    def teardown_method(self):
        Registry.mapping = original_registry_mapping

    def test_reads_test_config(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = Configuration.create("dummy name", test_config)
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
            Configuration.create("dummy name", test_config)

    def test_raises_on_unknown_processor(self):
        test_config = {
            "type": "unknown_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(UnknownComponentTypeError):
            Configuration.create("dummy name", test_config)

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
            Configuration.create("dummy name", test_config)

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
            Configuration.create("dummy name", test_config)

    def test_raises_if_multiple_mandatory_field_are_missing(self):
        test_config = {
            "type": "mock_processor",
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
        }
        with pytest.raises(
            TypeError,
            match=r"missing 2 required .* arguments: .*'specific_rules' and 'mandatory_attribute'",
        ):
            Configuration.create("dummy name", test_config)

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
            Configuration.create("dummy name", test_config)

    def test_init_non_mandatory_fields_with_default(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
        }
        config = Configuration.create("dummy name", test_config)
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
        config = Configuration.create("dummy name", test_config)
        assert config.optional_attribute == "I am optional"

    def test_init_optional_field_in_base_class(self):
        test_config = {
            "type": "mock_processor",
            "specific_rules": ["tests/testdata/unit/normalizer/rules/specific/"],
            "generic_rules": ["tests/testdata/unit/normalizer/rules/generic/"],
            "mandatory_attribute": "I am mandatory",
            "tree_config": "tests/testdata/unit/tree_config.json",
        }
        config = Configuration.create("dummy name", test_config)
        assert config.tree_config == "tests/testdata/unit/tree_config.json"
