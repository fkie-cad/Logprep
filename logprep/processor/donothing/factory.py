"""This module contains a factory to create donothing processors."""

from logging import Logger

from logprep.processor.processor_factory_error import (UnknownProcessorTypeError, InvalidConfigurationError)
from logprep.processor.base.factory import BaseFactory
from logprep.processor.donothing.processor import DoNothing


class DoNothingFactory(BaseFactory):
    """Create donothing processors."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> DoNothing:
        """Create a donothing processor."""
        DoNothingFactory._check_configuration(configuration)

        errors = configuration['errors'] if 'errors' in configuration else []
        extra_data = configuration['extra_data'] if 'extra_data' in configuration else None

        donothing = DoNothing(logger, errors, extra_data)

        return donothing

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'donothing'):
            raise UnknownProcessorTypeError
