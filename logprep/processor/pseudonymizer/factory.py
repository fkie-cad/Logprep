"""This module contains a Pseudonymizer that must be used to conform to EU privacy laws."""

from logging import Logger

import datetime

from logprep.processor.base.factory import BaseFactory
from logprep.processor.pseudonymizer.processor import Pseudonymizer


class PseudonymizerFactory(BaseFactory):
    """Create pseudonymizers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Pseudonymizer:
        """Create a pseudonymizer."""
        PseudonymizerFactory._check_configuration(configuration)

        pseudonymizer = Pseudonymizer(name=name, configuration=configuration, logger=logger)

        return pseudonymizer

    @staticmethod
    def _check_configuration(configuration: dict):
        PseudonymizerFactory._check_common_configuration(
            "pseudonymizer",
            [
                "pubkey_analyst",
                "pubkey_depseudo",
                "hash_salt",
                "pseudonyms_topic",
                "specific_rules",
                "generic_rules",
                "regex_mapping",
                "max_cached_pseudonyms",
                "max_caching_days",
                "tld_list",
            ],
            configuration,
        )
