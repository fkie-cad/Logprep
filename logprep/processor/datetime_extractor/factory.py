"""This module contains a factory for DateTimeExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.datetime_extractor.processor import DateTimeExtractor


class DateTimeExtractorFactory(BaseFactory):
    """Create datetime extractor."""

    mandatory_fields = ["generic_rules", "specific_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DateTimeExtractor:
        """Create a datetime extractor."""
        DateTimeExtractorFactory._check_configuration(configuration)

        return DateTimeExtractor(name=name, configuration=configuration, logger=logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        DateTimeExtractorFactory._check_common_configuration(
            processor_type="datetime_extractor",
            existing_items=DateTimeExtractorFactory.mandatory_fields,
            configuration=configuration,
        )
