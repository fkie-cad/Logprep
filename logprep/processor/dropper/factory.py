"""This module contains a factory for Dropper processors."""

from logprep.processor.processor_factory_error import UnknownProcessorTypeError, InvalidConfigurationError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.dropper.processor import Dropper


class DropperFactory(BaseFactory):
    """Create droppers."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> Dropper:
        """Create a dropper."""
        DropperFactory._check_configuration(configuration)

        dropper = Dropper(name, logger)
        dropper.add_rules_from_directory(configuration['rules'])

        return dropper

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'dropper'):
            raise UnknownProcessorTypeError

        for item in ('rules',):
            if item not in configuration:
                raise InvalidConfigurationError(
                    f'Item {item} is missing in Dropper configuration')
