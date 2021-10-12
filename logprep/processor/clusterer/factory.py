"""This module contains a factory for the cluster processor."""

from logging import Logger

from logprep.processor.processor_factory_error import UnknownProcessorTypeError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.clusterer.processor import Clusterer
from logprep.processor.base.exceptions import (InvalidRuleFileError, NotARulesDirectoryError,
                                               KeyDoesnotExistInSchemaError,
                                               InvalidRuleConfigurationError,
                                               InvalidConfigurationError)


class ClustererFactory(BaseFactory):
    """Create clusterers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Clusterer:
        """Create a clusterer."""
        ClustererFactory._check_configuration(configuration)

        clusterer = Clusterer(name, configuration.get('tree_config'), logger)

        try:
            clusterer.add_rules_from_directory(configuration['rules'])
        except (InvalidRuleFileError, NotARulesDirectoryError,
                KeyDoesnotExistInSchemaError) as error:
            raise InvalidRuleConfigurationError(str(error)) from error

        return clusterer

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'clusterer'):
            raise UnknownProcessorTypeError

        for item in ('rules', 'output_field_name'):
            if item not in configuration:
                raise InvalidConfigurationError(
                    'Item "' + item + '" is missing in Clusterer configuration')
