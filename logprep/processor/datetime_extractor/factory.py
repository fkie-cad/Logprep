"""This module contains a factory for DateTimeExtractor processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.datetime_extractor.processor import DatetimeExtractor
from logprep.processor.processor_factory_error import InvalidConfigurationError


class DatetimeExtractorFactory(BaseFactory):
    """Create datetime extractor."""

    mandatory_fields = ["generic_rules", "specific_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DatetimeExtractor:
        """Create a datetime extractor."""
        DatetimeExtractorFactory._check_configuration(configuration)

        return DatetimeExtractor(name=name, configuration=configuration, logger=logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        DatetimeExtractorFactory._check_common_configuration(
            processor_type="datetime_extractor",
            existing_items=DatetimeExtractorFactory.mandatory_fields,
            configuration=configuration,
        )
        for field in DatetimeExtractorFactory.mandatory_fields:
            if field not in configuration.keys():
                raise InvalidConfigurationError
