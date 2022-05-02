"""This module contains a factory for pre-detector processors."""

from logging import Logger

from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.selective_extractor.processor import SelectiveExtractor


class InvalidSelectiveExtractorFactoryConfigurationError(InvalidConfigurationError):
    """Base class for SelectiveExtractorFactory specific exceptions."""


class SelectiveExtractorFactory(BaseFactory):
    """Create selective extractors."""

    mandatory_fields = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger):
        """Create a selective extractor."""
        SelectiveExtractorFactory._check_configuration(configuration)

        return SelectiveExtractor(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        """Check if the processor configuration has the mandatory fields."""
        SelectiveExtractorFactory._check_common_configuration(
            "selective_extractor", SelectiveExtractorFactory.mandatory_fields, configuration
        )
