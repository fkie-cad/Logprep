"""This module contains a factory for DomainResolver processors."""

import datetime

from logprep.processor.base.factory import BaseFactory
from logprep.processor.domain_resolver.processor import DomainResolver


class DomainResolverFactory(BaseFactory):
    """Create domain resolver."""

    mandatory_fields = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DomainResolver:
        """Create a domain resolver."""
        DomainResolverFactory._check_configuration(configuration)

        return DomainResolver(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        DomainResolverFactory._check_common_configuration(
            "domain_resolver", DomainResolverFactory.mandatory_fields, configuration
        )
