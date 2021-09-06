"""This module contains a factory for normalizer processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.normalizer.processor import Normalizer


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
            configuration.get('tree_config'),
            logger,
            configuration['regex_mapping'],
            configuration.get('html_replace_fields'),
            configuration.get('grok_patterns'))

        return normalizer

    @staticmethod
    def _check_configuration(configuration: dict):
        NormalizerFactory._check_common_configuration('normalizer',
                                                      ['specific_rules', 'generic_rules',
                                                       'regex_mapping'],
                                                      configuration)
