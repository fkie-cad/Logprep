"""This module contains a factory for GenericResolver processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.generic_resolver.processor import GenericResolver


class GenericResolverFactory(BaseFactory):
    """Create generic resolver."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GenericResolver:
        """Create a generic resolver."""
        GenericResolverFactory._check_configuration(configuration)

        generic_resolver = GenericResolver(name, configuration['tree_config'], logger)
        generic_resolver.add_rules_from_directory(configuration['rules'])

        return generic_resolver

    @staticmethod
    def _check_configuration(configuration: dict):
        GenericResolverFactory._check_common_configuration('generic_resolver', ['rules'],
                                                           configuration)
