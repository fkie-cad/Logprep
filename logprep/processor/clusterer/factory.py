"""This module contains a factory for the cluster processor."""

from logging import Logger

from logprep.processor.processor_factory_error import UnknownProcessorTypeError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.clusterer.processor import Clusterer
from logprep.processor.base.exceptions import (
    InvalidRuleFileError,
    NotARulesDirectoryError,
    KeyDoesnotExistInSchemaError,
    InvalidRuleConfigurationError,
    InvalidConfigurationError,
)


class ClustererFactory(BaseFactory):
    """Create clusterers."""

    mandatory_items = ("type", "specific_rules", "generic_rules", "output_field_name")

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Clusterer:
        """Create a clusterer."""
        ClustererFactory._check_configuration(configuration)

        return Clusterer(name, logger, **configuration)

    @staticmethod
    def _check_configuration(configuration: dict):

        for item in ClustererFactory.mandatory_items:
            if item not in configuration:
                raise InvalidConfigurationError(
                    'Item "' + item + '" is missing in Clusterer configuration'
                )

        if not isinstance(configuration.get("type"), str):
            raise UnknownProcessorTypeError

        if configuration.get("type").lower() != "clusterer":
            raise UnknownProcessorTypeError
