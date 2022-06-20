"""This module contains a factory to create processors."""
from typing import TYPE_CHECKING

from logprep.abc import Processor
from logprep.processor.processor_configuration import ProcessorConfiguration
from logprep.processor.processor_factory_error import (
    InvalidConfigSpecificationError,
    InvalidConfigurationError,
    NotExactlyOneEntryInConfigurationError,
)

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


class ProcessorFactory:
    """Create processors."""

    @classmethod
    def create(cls, configuration: dict, logger: "Logger") -> Processor:
        """Create processor."""
        if not configuration:
            raise NotExactlyOneEntryInConfigurationError()
        if len(configuration) > 1:
            raise InvalidConfigurationError(
                "There must be exactly one processor definition per pipeline entry."
            )
        for processor_name, processor_configuration_dict in configuration.items():
            if not isinstance(processor_configuration_dict, dict):
                raise InvalidConfigSpecificationError()
            processor = ProcessorConfiguration.get_processor_class(
                processor_name, processor_configuration_dict
            )
            processor_configuration = ProcessorConfiguration.create(
                processor_name, processor_configuration_dict
            )
            return processor(processor_name, processor_configuration, logger)
