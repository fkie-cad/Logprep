"""This module contains a factory for GenericAdder processors."""
import re

from logprep.processor.base.factory import BaseFactory
from logprep.processor.generic_adder.processor import GenericAdder
from logprep.processor.processor_factory_error import InvalidConfigurationError


class GenericAdderFactory(BaseFactory):
    """Create generic adder."""

    mandatory_fields = ["generic_rules", "specific_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GenericAdder:
        """Create a configured generic adder with loaded rules.

        Parameters
        ----------
        name : str
           Name for the generic adder that will be created.
        configuration : dict
           Parsed configuration YML used for the generic adder.
        logger : logging.Logger
           Logger to use.

        Returns
        -------
        GenericAdder
            A configured generic adder instance with loaded rules.

        """
        GenericAdderFactory._check_configuration(configuration)
        return GenericAdder(name, configuration, logger)

    @staticmethod
    def _check_configuration(configuration: dict):
        """Check the configuration for the generic adder.

        It must contain a generic adder configuration and at least one rule path.

        Parameters
        ----------
        configuration : dict
           Parsed configuration YML used for the generic adder.

        """
        GenericAdderFactory._check_common_configuration(
            "generic_adder", GenericAdderFactory.mandatory_fields, configuration
        )

        table = configuration.get("sql_config", {}).get("table")
        if table and re.search(r"\s", table):
            raise InvalidConfigurationError(f"Table in 'sql_config' contains whitespaces!")
