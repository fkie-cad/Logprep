"""This module contains a factory for HyperscanResolver processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.hyperscan_resolver.processor import HyperscanResolver


class HyperscanResolverFactory(BaseFactory):
    """Create HyperscanResolver."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> HyperscanResolver:
        """Create a HyperscanResolver."""
        HyperscanResolverFactory._check_configuration(configuration)

        return HyperscanResolver(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        HyperscanResolverFactory._check_common_configuration(
            "hyperscan_resolver", ["specific_rules", "generic_rules"], configuration
        )
