"""This module contains a factory for Dropper processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.dropper.processor import Dropper


class DropperFactory(BaseFactory):
    """Create droppers."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> Dropper:
        """Create a dropper."""
        DropperFactory._check_configuration(configuration)

        dropper = Dropper(name, configuration.get("tree_config"), logger)
        dropper.add_rules_from_directory(configuration["rules"])

        return dropper

    @staticmethod
    def _check_configuration(configuration: dict):
        DropperFactory._check_common_configuration("dropper", ["rules"], configuration)
