"""
DomainResolver
==============

The `domain_resolver` is a processor that can resolve domains inside a defined field.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - domainresolvername:
        type: domain_resolver
        rules:
            - tests/testdata/rules/rules
        timeout: 0.5
        max_cached_domains: 20000
        max_caching_days: 1
        hash_salt: secure_salt
        cache_enabled: true
        debug_cache: false

.. autoclass:: logprep.processor.domain_resolver.processor.DomainResolver.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.domain_resolver.rule
"""

import datetime
import logging
import socket
from enum import IntEnum
from functools import cached_property
from multiprocessing import context
from multiprocessing.pool import ThreadPool
from typing import Optional, Any
from urllib.parse import urlsplit

from attr import define, field, validators

from logprep.abc.processor import Processor
from logprep.metrics.metrics import CounterMetric
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_fields_to, get_dotted_field_value

logger = logging.getLogger("DomainResolver")


class ResolveStatus(IntEnum):
    """Status of resolving domains"""

    SUCCESS = 0
    """Resolving the domain was successful"""
    TIMEOUT = 1
    """Domain resolver timeout while trying to resolve the domain (this is not a socket timeout)"""
    INVALID = 2
    """The resolved domain was invalid and thus not resolved"""
    UNKNOWN = 3
    """Tried to resolve the domain, but the domain is unknown"""


class DomainResolver(Processor):
    """Resolve domains."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """DomainResolver config"""

        timeout: Optional[float] = field(
            default=0.5,
            validator=validators.optional(validators.instance_of(float)),
            converter=float,
        )
        """Timeout for resolving of domains."""
        max_cached_domains: int = field(validator=validators.instance_of(int))
        """The maximum number of cached domains. One cache entry requires ~250 Byte, thus 10
        million elements would require about 2.3 GB RAM. The cache is not persisted. Restarting
        Logprep does therefore clear the cache."""
        max_caching_days: int = field(validator=validators.instance_of(int))
        """Number of days a domains is cached after the last time it appeared.
        This caching reduces the CPU load of Logprep (no demanding encryption must be performed
        repeatedly) and the load on subsequent components (i.e. Logstash or Opensearch).
        Setting the caching days to Null deactivates the caching. In case the cache size has been
        exceeded (see `domain_resolver.max_cached_domains`),the oldest cached pseudonyms will
        be discarded first.Thus, it is possible that a domain is re-added to the cache before
        max_caching_days has elapsed if it was discarded due to the size limit."""
        hash_salt: str = field(validator=validators.instance_of(str))
        """A salt that is used for hashing."""
        cache_enabled: bool = field(
            default=True, validator=validators.optional(validator=validators.instance_of(bool))
        )
        """If enabled activates a cache such that already seen domains do not need to be resolved
        again."""
        debug_cache: bool = field(
            default=False, validator=validators.optional(validator=validators.instance_of(bool))
        )
        """If enabled adds debug information to the current event, for example if the event
        was retrieved from the cache or newly resolved, as well as the cache size."""

    @define(kw_only=True)
    class Metrics(Processor.Metrics):
        """Tracks statistics about the DomainResolver"""

        total_urls: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of all resolved urls",
                name="domain_resolver_total_urls",
            )
        )
        """Number of all resolved urls"""
        resolved_new: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of urls that had to be resolved newly",
                name="domain_resolver_resolved_new",
            )
        )
        """Number of urls that had to be resolved newly"""
        resolved_cached: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of urls that were resolved from cache",
                name="domain_resolver_resolved_cached",
            )
        )
        """Number of urls that were resolved from cache"""
        timeouts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of timeouts that occurred while resolving a url",
                name="domain_resolver_timeouts",
            )
        )
        """Number of timeouts that occurred while resolving a url"""
        invalid_domains: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of invalid domains",
                name="domain_resolver_invalid_domains",
            )
        )
        """Number of invalid domains that were trying to be resolved"""
        unknown_domains: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of unknown domains",
                name="domain_resolver_unknown_domains",
            )
        )
        """Number of unknown domains that were trying to be resolved"""

    __slots__ = ["_domain_ip_map"]

    _domain_ip_map: dict[str, Optional[str]]

    rule_class = DomainResolverRule

    def __init__(self, name: str, configuration: Processor.Config):
        super().__init__(name, configuration)
        self._domain_ip_map = {}

    @cached_property
    def _cache(self) -> Cache:
        cache_max_timedelta = datetime.timedelta(days=self._config.max_caching_days)
        return Cache(max_items=self._config.max_cached_domains, max_timedelta=cache_max_timedelta)

    @cached_property
    def _hasher(self) -> SHA256Hasher:
        return SHA256Hasher()

    @cached_property
    def _thread_pool(self) -> ThreadPool:
        return ThreadPool(processes=1)

    def _apply_rules(self, event: dict[str, Any], rule: DomainResolverRule) -> None:
        source_field = rule.source_fields[0]
        domain_or_url_str = get_dotted_field_value(event, source_field)
        if not domain_or_url_str:
            return

        url = urlsplit(domain_or_url_str)
        domain = url.hostname
        if url.scheme == "":
            domain = url.path
        if not domain:
            return
        self.metrics.total_urls += 1
        if self._config.cache_enabled:
            self._resolve_with_cache(domain, event, rule)
        else:
            resolved_ip, _ = self._resolve_ip(domain)
            self._add_resolve_infos_to_event(event, rule, resolved_ip)

    def _resolve_with_cache(
        self, domain: str, event: dict[str, Any], rule: DomainResolverRule
    ) -> None:
        hash_string = self._hasher.hash_str(domain, salt=self._config.hash_salt)
        requires_storing = self._cache.requires_storing(hash_string)
        if requires_storing:
            resolved_ip, status = self._resolve_ip(domain)
            if status in (ResolveStatus.SUCCESS, ResolveStatus.UNKNOWN, ResolveStatus.TIMEOUT):
                self._domain_ip_map.update({hash_string: resolved_ip})
            self.metrics.resolved_new += 1
        else:
            resolved_ip = self._domain_ip_map.get(hash_string)
            self.metrics.resolved_cached += 1
        self._add_resolve_infos_to_event(event, rule, resolved_ip)

        if self._config.debug_cache:
            self._store_debug_infos(event, requires_storing)

    def _add_resolve_infos_to_event(
        self, event: dict[str, Any], rule: DomainResolverRule, resolved_ip: Optional[str]
    ) -> None:
        if resolved_ip:
            self._write_target_field(event, rule, resolved_ip)

    def _resolve_ip(self, domain: str) -> tuple[Optional[str], int]:
        """Resolve domain with timeout.

        Assumes socket default timeout is None and relies on threading to create a timeout.
        """
        try:
            result = self._thread_pool.apply_async(socket.gethostbyname, (domain,))
            resolved_ip = result.get(timeout=self._config.timeout)
            return resolved_ip, ResolveStatus.SUCCESS
        except ValueError:  # Makes no connection so does not need to be cached
            self.metrics.invalid_domains += 1
            return None, ResolveStatus.INVALID
        except context.TimeoutError:
            self.metrics.timeouts += 1
            return None, ResolveStatus.TIMEOUT
        except OSError:  # Won't be timeout if default timeout is None
            self.metrics.unknown_domains += 1
            return None, ResolveStatus.UNKNOWN

    def _store_debug_infos(self, event: dict[str, Any], requires_storing: bool) -> None:
        event_dbg = {
            "resolved_ip_debug": {
                "obtained_from_cache": not requires_storing,
                "cache_size": len(self._domain_ip_map.keys()),
            }
        }
        add_fields_to(event, event_dbg, overwrite_target=True)
