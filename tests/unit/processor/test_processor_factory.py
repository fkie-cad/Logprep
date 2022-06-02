# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-lines
from logging import getLogger
from random import sample
from string import ascii_letters
from unittest import mock

from pytest import raises

from logprep.processor.clusterer.processor import Clusterer
from logprep.processor.labeler.processor import Labeler
from logprep.processor.normalizer.processor import Normalizer
from logprep.processor.processor_factory import ProcessorFactory
from logprep.processor.processor_factory_error import (
    InvalidConfigurationError,
    UnknownProcessorTypeError,
    NotExactlyOneEntryInConfigurationError,
    NoTypeSpecifiedError,
    InvalidConfigSpecificationError,
)
from logprep.processor.pseudonymizer.processor import Pseudonymizer
from tests.testdata.metadata import path_to_schema, path_to_single_rule

logger = getLogger()


def test_create_fails_for_an_empty_section():
    with raises(
        NotExactlyOneEntryInConfigurationError,
        match="There must be exactly one processor definition per pipeline entry.",
    ):
        ProcessorFactory.create({}, logger)


def test_create_fails_if_config_is_not_an_object():
    with raises(
        InvalidConfigSpecificationError,
        match="The processor configuration must be specified as an object.",
    ):
        ProcessorFactory.create({"processorname": "string"}, logger)


def test_create_fails_if_config_does_not_contain_type():
    with raises(NoTypeSpecifiedError, match="The processor type specification is missing"):
        ProcessorFactory.create({"processorname": {"other": "value"}}, logger)


def test_create_fails_for_unknown_type():
    for type_name in ["unknown", "no such processor"] + [
        "".join(sample(ascii_letters, 6)) for i in range(5)
    ]:
        with raises(UnknownProcessorTypeError):
            ProcessorFactory.create({"processorname": {"type": type_name}}, logger)


def test_create_pseudonymizer_returns_pseudonymizer_processor():
    processor = ProcessorFactory.create(
        {
            "pseudonymizer": {
                "type": "pseudonymizer",
                "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
                "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
                "hash_salt": "a_secret_tasty_ingredient",
                "specific_rules": ["tests/testdata/unit/pseudonymizer/rules/specific"],
                "generic_rules": ["tests/testdata/unit/pseudonymizer/rules/generic"],
                "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
                "pseudonyms_topic": "pseudonyms",
                "max_cached_pseudonyms": 1000000,
                "max_caching_days": 1,
            }
        },
        logger,
    )

    assert isinstance(processor, Pseudonymizer)


def test_create_normalizer_returns_normalizer_processor():
    processor = ProcessorFactory.create(
        {
            "normalizer": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/unit/normalizer/rules/specific"],
                "generic_rules": ["tests/testdata/unit/normalizer/rules/generic"],
                "regex_mapping": "tests/testdata/unit/normalizer/regex_mapping.yml",
            }
        },
        logger,
    )

    assert isinstance(processor, Normalizer)


def test_create_clusterer_returns_clusterer_processor():
    processor = ProcessorFactory.create(
        {
            "clusterer": {
                "type": "clusterer",
                "output_field_name": "cluster_signature",
                "specific_rules": ["tests/testdata/unit/clusterer/rules/specific"],
                "generic_rules": ["tests/testdata/unit/clusterer/rules/generic"],
            }
        },
        logger,
    )

    assert isinstance(processor, Clusterer)


def test_fails_when_section_contains_more_than_one_element():
    with raises(
        InvalidConfigurationError,
        match="There must be exactly one processor definition per pipeline entry.",
    ):
        ProcessorFactory.create({"first": mock.MagicMock(), "second": mock.MagicMock()}, logger)


def test_create_labeler_creates_labeler_processor():
    processor = ProcessorFactory.create(
        {
            "labelername": {
                "type": "labeler",
                "schema": path_to_schema,
                "generic_rules": [path_to_single_rule],
                "specific_rules": [path_to_single_rule],
            }
        },
        logger,
    )

    assert isinstance(processor, Labeler)
