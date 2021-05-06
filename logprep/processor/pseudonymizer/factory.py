"""This module contains a Pseudonymizer that must be used to conform to EU privacy laws."""

from logging import Logger

import datetime

from logprep.processor.base.factory import BaseFactory
from logprep.processor.pseudonymizer.processor import Pseudonymizer
from logprep.processor.processor_factory_error import UnknownProcessorTypeError, InvalidConfigurationError


class PseudonymizerFactory(BaseFactory):
    """Create pseudonymizers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Pseudonymizer:
        """Create a pseudonymizer."""
        PseudonymizerFactory._check_configuration(configuration)

        max_timedelta = datetime.timedelta(days=configuration["max_caching_days"])

        pseudonymizer = Pseudonymizer(
            name,
            configuration["pubkey_analyst"],
            configuration["pubkey_depseudo"],
            configuration["hash_salt"],
            configuration["pseudonyms_topic"],
            configuration["regex_mapping"],
            configuration["max_cached_pseudonyms"],
            max_timedelta,
            configuration.get("tld_list"),
            logger)

        pseudonymizer.setup()
        pseudonymizer.add_rules_from_directory(configuration["specific_rules"], configuration["generic_rules"])

        return pseudonymizer

    @staticmethod
    def _check_configuration(configuration: dict):
        if 'type' not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration['type'], str)) or (
                configuration['type'].lower() != 'pseudonymizer'):
            raise UnknownProcessorTypeError

        for item in ("pubkey_analyst", "pubkey_depseudo", "hash_salt", "pseudonyms_topic",
                     "specific_rules", "generic_rules", "regex_mapping", "max_cached_pseudonyms",
                     "max_caching_days", "tld_list"):
            if item not in configuration:
                raise InvalidConfigurationError(
                    f"Item \"{item}\" is missing in Pseudonymizer configuration")
