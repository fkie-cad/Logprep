"""This module contains a factory for normalizer processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.normalizer.processor import Normalizer
from logprep.processor.processor_factory_error import UnknownProcessorTypeError, InvalidConfigurationError


class NormalizerFactory(BaseFactory):
    """Create normalizers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Normalizer:
        """Create a normalizer."""
        NormalizerFactory._check_configuration(configuration)

        normalizer = Normalizer(
            name,
            configuration['specific_rules'],
            configuration['generic_rules'],
            logger,
            configuration['regex_mapping'],
            configuration.get('grok_patterns'))

        return normalizer

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'normalizer'):
            raise UnknownProcessorTypeError

        for item in ('specific_rules', 'generic_rules', 'regex_mapping'):
            if item not in configuration:
                raise InvalidConfigurationError(
                    f'Item "{item}" is missing in Normalizer configuration')
