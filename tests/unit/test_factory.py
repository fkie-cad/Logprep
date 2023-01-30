# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-lines
import re
from logging import getLogger
from random import sample
from string import ascii_letters
from unittest import mock

from pytest import raises, mark

from logprep.abc.input import Input
from logprep.factory import Factory
from logprep.factory_error import (
    InvalidConfigurationError,
    UnknownComponentTypeError,
    NoTypeSpecifiedError,
    InvalidConfigSpecificationError,
)
from logprep.processor.clusterer.processor import Clusterer
from logprep.processor.labeler.processor import Labeler
from logprep.processor.normalizer.processor import Normalizer
from logprep.processor.pseudonymizer.processor import Pseudonymizer
from tests.testdata.metadata import path_to_schema, path_to_single_rule

logger = getLogger()


@mark.parametrize(
    ["configs", "error", "message"],
    [
        ((None, {}), InvalidConfigurationError, r"The component definition is empty\."),
        (
            ("string", 1, True, ["string"], [], "", 0, False),
            InvalidConfigSpecificationError,
            r"The configuration must be specified as an object\.",
        ),
        (
            ({"foo": None},),
            InvalidConfigurationError,
            'The definition of component "foo" is empty.',
        ),
        (
            ({"foo": {}}, {"foo": {"other": "value"}}),
            NoTypeSpecifiedError,
            "The type specification is missing for element with name 'foo'",
        ),
        (
            ({"foo": value} for value in ("string", 1, True, ["string"], [], "", 0, False)),
            InvalidConfigSpecificationError,
            r'The configuration for component "foo" must be specified as an object\.',
        ),
    ],
)
def test_create_from_dict_validates_config(configs, error, message):
    for config in configs:
        with raises(error) as exception_info:
            Factory.create(config, logger)
        value = str(exception_info.value)
        assertion_error_message = (
            f'Error message of "{error.__name__}" did not match regex for test input '
            + f'"{repr(config)}".\n Regex pattern: {message}\n Error message: {value}"'
        )
        if not re.search(message, value):
            raise AssertionError(assertion_error_message)


def test_create_fails_for_unknown_type():
    for type_name in ["unknown", "no such processor"] + [
        "".join(sample(ascii_letters, 6)) for i in range(5)
    ]:
        with raises(UnknownComponentTypeError):
            Factory.create({"processorname": {"type": type_name}}, logger)


def test_create_pseudonymizer_returns_pseudonymizer_processor():
    processor = Factory.create(
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
    processor = Factory.create(
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
    processor = Factory.create(
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
        match=r"Found multiple component definitions \(first, second\), "
        r"but there must be exactly one\.",
    ):
        Factory.create({"first": mock.MagicMock(), "second": mock.MagicMock()}, logger)


def test_create_labeler_creates_labeler_processor():
    processor = Factory.create(
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


def test_dummy_input_creates_dummy_input_connector():
    processor = Factory.create(
        {"labelername": {"type": "dummy_input", "documents": [{}, {}]}},
        logger,
    )

    assert isinstance(processor, Input)
