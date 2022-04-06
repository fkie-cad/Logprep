"""This module contains a factory for GenericAdder processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.generic_adder.processor import GenericAdder


class GenericAdderFactory(BaseFactory):
    """Create generic adder."""

    mandatory_fields = ["generic_rules", "specific_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GenericAdder:
        """Create a generic adder."""
        GenericAdderFactory._check_configuration(configuration)
        return GenericAdder(name, configuration, logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        GenericAdderFactory._check_common_configuration(
            "generic_adder", GenericAdderFactory.mandatory_fields, configuration
        )
