"""This module contains a factory for DomainResolver processors."""

import datetime

from logprep.processor.base.factory import BaseFactory
from logprep.processor.domain_resolver.processor import DomainResolver


class DomainResolverFactory(BaseFactory):
    """Create domain resolver."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> DomainResolver:
        """Create a domain resolver."""
        DomainResolverFactory._check_configuration(configuration)

        max_timedelta = datetime.timedelta(days=configuration["max_caching_days"])

        domain_resolver = DomainResolver(name,
                                         configuration['tree_config'],
                                         configuration['tld_list'],
                                         configuration.get('timeout', 0.5),
                                         configuration['max_cached_domains'],
                                         max_timedelta,
                                         configuration['hash_salt'],
                                         configuration.get('cache_enabled', True),
                                         configuration.get('debug_cache', False),
                                         logger)
        domain_resolver.add_rules_from_directory(configuration['rules'])

        return domain_resolver

    @staticmethod
    def _check_configuration(configuration: dict):
        DomainResolverFactory._check_common_configuration('domain_resolver', ['rules'],
                                                          configuration)
