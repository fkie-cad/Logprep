"""This module contains a factory for DateTimeExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.datetime_extractor.processor import DateTimeExtractor
from logprep.processor.processor_factory_error import InvalidConfigurationError


class DateTimeExtractorFactory(BaseFactory):
    """Create datetime extractor."""

    mandatory_fields = ["type", "generic_rules", "specific_rules", "tree_config"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DateTimeExtractor:
        """Create a datetime extractor."""
        DateTimeExtractorFactory._check_configuration(configuration)

        return DateTimeExtractor(name=name, configuration=configuration, logger=logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        for field in DateTimeExtractorFactory.mandatory_fields:
            if field not in configuration.keys():
                raise InvalidConfigurationError
