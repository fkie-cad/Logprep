"""This module contains a factory for DateTimeExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.datetime_extractor.processor import DateTimeExtractor


class DateTimeExtractorFactory(BaseFactory):
    """Create datetime extractor."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DateTimeExtractor:
        """Create a datetime extractor."""
        DateTimeExtractorFactory._check_configuration(configuration)

        datetime_extractor = DateTimeExtractor(name, configuration.get('tree_config'), logger)
        datetime_extractor.add_rules_from_directory(configuration['rules'])

        return datetime_extractor

    @staticmethod
    def _check_configuration(configuration: dict):
        DateTimeExtractorFactory._check_common_configuration('datetime_extractor', ['rules'],
                                                             configuration)
