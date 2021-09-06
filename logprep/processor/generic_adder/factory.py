"""This module contains a factory for GenericAdder processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.generic_adder.processor import GenericAdder


class GenericAdderFactory(BaseFactory):
    """Create generic adder."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GenericAdder:
        """Create a generic adder."""
        GenericAdderFactory._check_configuration(configuration)

        generic_adder = GenericAdder(name, configuration['tree_config'], logger)
        generic_adder.add_rules_from_directory(configuration['rules'])

        return generic_adder

    @staticmethod
    def _check_configuration(configuration: dict):
        GenericAdderFactory._check_common_configuration('generic_adder', ['rules'],
                                                        configuration)
