"""This module contains a do delete processor."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.delete.processor import Delete


class DeleteFactory(BaseFactory):
    """Create delete processor."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Delete:
        """Create a delete processor."""
        DeleteFactory._check_configuration(configuration)

        return Delete(name=name, configuration=configuration, logger=logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        DeleteFactory._check_common_configuration("delete", [], configuration)
