"""This module contains a factory for Dropper processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.dropper.processor import Dropper


class DropperFactory(BaseFactory):
    """Create droppers."""

    mandatory_fields = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> Dropper:
        """Create a dropper."""
        DropperFactory._check_configuration(configuration)

        return Dropper(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        DropperFactory._check_common_configuration(
            "dropper", DropperFactory.mandatory_fields, configuration
        )
