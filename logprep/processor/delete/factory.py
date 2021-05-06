"""This module contains a do delete processor."""

from logging import Logger

from logprep.processor.processor_factory_error import UnknownProcessorTypeError, InvalidConfigurationError
from logprep.processor.base.factory import BaseFactory
from logprep.processor.delete.processor import Delete


class DeleteFactory(BaseFactory):
    """Create delete processor."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Delete:
        """Create a delete processor."""
        DeleteFactory._check_configuration(configuration)

        delete = Delete(configuration['i_really_want_to_delete_all_log_events'])

        return delete

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'delete'):
            raise UnknownProcessorTypeError
