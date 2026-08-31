"""
|PROCESSOR_NAME|
================

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
        lifetime: 1.0
        max_cached_domains: 20000
        max_caching_days: 1
        hash_salt: secure_salt
        cache_enabled: true

.. autoclass:: logprep.processor.domain_resolver.processor.DomainResolver.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.domain_resolver.rule
"""

import datetime
import logging
import typing
from enum import IntEnum
from functools import cached_property
from typing import Optional
from urllib.parse import urlsplit

from attr import define, field, validators
from dns.exception import Timeout, FormError, SyntaxError as DNSSyntaxError, TooBig
from dns.resolver import Resolver, NXDOMAIN, LifetimeTimeout, NoAnswer, NoNameservers

from logprep.abc.processor import Processor
from logprep.metrics.metrics import CounterMetric
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache, Timer
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import get_dotted_field_value

logger = logging.getLogger("DomainResolver")


class FailureType(IntEnum):
    """Status of resolving domains"""

    TIMEOUT = 0
    """Domain resolver timeout while trying to resolve the domain (this is not a socket timeout)"""
    INVALID = 1
    """The resolved domain was invalid and thus not resolved"""
    UNKNOWN = 2
    """Tried to resolve the domain, but the domain is unknown"""
    NO_ANSWER = 3
    """The resolved domain was valid, but returned no data"""
    NO_NAMESERVERS = 4
    """Nameservers do not exist or timed out"""


@define
class SuccessResult:
    resolved_ip: str


@define
class FailedResult:
    failure_type: FailureType
    error: Exception | None = None


class DomainResolver(Processor):
    """Resolve domains."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Config for |PROCESSOR|"""

        timeout: float = field(
            default=0.5,
            validator=validators.instance_of(float),
            converter=float,
        )
        """Timeout for resolving of domains.

        .. security-best-practice::
           :title: |PROCESSOR| - Timeout

           Ensure to set this to a reasonable value to avoid DOS attacks by malicious domains in
           your logs. The default is set to 0.5 seconds.
        """
        lifetime: float = field(
            default=1.0, validator=validators.optional(validators.instance_of(float))
        )
        """Total timeout for resolving of domains including multiple attempts."""
        max_cached_domains: int = field(validator=validators.instance_of(int))
        """The maximum number of cached domains. One cache entry requires ~250 Byte, thus 10
        million elements would require about 2.3 GB RAM. The cache is not persisted. Restarting
        Logprep does therefore clear the cache.

        .. security-best-practice::
           :title: |PROCESSOR| - Max Cached Domains

           Ensure to set this to a reasonable value to avoid excessive memory usage
           and OOM situations by the domain resolver cache.

        """
        timeout_block_time: float = field(default=5.0, validator=validators.instance_of(float))
        """Minutes after which a timed out domain can be resolved again."""
        cache_prune_interval: float = field(default=3600.0, validator=validators.instance_of(float))
        """Seconds after which decayed domains are pruned from caches."""
        max_caching_days: int = field(validator=validators.instance_of(int))
        """Number of days a domains is cached after the last time it appeared.
        This caching reduces the CPU load of Logprep (no demanding encryption must be performed
        repeatedly) and the load on subsequent components (i.e. Logstash or Opensearch).
        Setting the caching days to Null deactivates the caching. In case the cache size has been
        exceeded (see `domain_resolver.max_cached_domains`),the oldest cached resolved domains will
        be discarded first.Thus, it is possible that a domain is re-added to the cache before
        max_caching_days has elapsed if it was discarded due to the size limit."""
        hash_salt: str = field(validator=validators.instance_of(str))
        """A salt that is used for hashing."""
        cache_enabled: bool = field(default=True, validator=validators.instance_of(bool))
        """If enabled activates a cache such that already seen domains do not need to be resolved
        again."""

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
        resolved_domains: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of domains that were successfully resolved",
                name="domain_resolver_resolved_domains",
            )
        )
        """Number of domains that were successfully resolved"""
        timeouts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of timeouts that occurred while resolving a url",
                name="domain_resolver_timeouts",
            )
        )
        """Number of timeouts that occurred while resolving a url"""
        timeouts_cached: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of timeouts from the timeout cache for a url",
                name="domain_resolver_timeouts_cached",
            )
        )
        """Number of timeouts from the timeout cache for a url"""
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

    _domain_ip_map: dict[str, Optional[SuccessResult | FailedResult]]

    rule_class = DomainResolverRule

    def __init__(self, name: str, configuration: Processor.Config):
        super().__init__(name, configuration)
        self._domain_ip_map = {}

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(DomainResolver.Config, self._config)

    @cached_property
    def _dns_resolver(self) -> Resolver:
        dns_resolver = Resolver()
        dns_resolver.timeout = self.config.timeout
        dns_resolver.lifetime = self.config.lifetime
        return dns_resolver

    @cached_property
    def _timeout_cache(self) -> Cache:
        cache_max_timedelta = datetime.timedelta(minutes=self.config.timeout_block_time)
        cache = Cache(
            max_items=self.config.max_cached_domains,
            max_timedelta=cache_max_timedelta,
            prune_interval=self.config.cache_prune_interval,
        )
        return cache

    @cached_property
    def _domain_cache(self) -> Cache:
        cache_max_timedelta = datetime.timedelta(days=self.config.max_caching_days)
        cache = Cache(
            max_items=self.config.max_cached_domains,
            max_timedelta=cache_max_timedelta,
            prune_interval=self.config.cache_prune_interval,
        )
        return cache

    @cached_property
    def _domain_ip_map_prune_timer(self) -> Timer:
        return Timer(self.config.cache_prune_interval)

    @cached_property
    def _hasher(self) -> SHA256Hasher:
        return SHA256Hasher()

    def _apply_rules(self, event: dict[str, typing.Any], rule: DomainResolverRule):
        self._timeout_cache.prune_decayed()
        self._domain_cache.prune_decayed()
        self._prune_domain_ip_map()
        source_field = rule.source_fields[0]
        domain_or_url_str = get_dotted_field_value(event, source_field)
        if not domain_or_url_str:
            return

        url = urlsplit(domain_or_url_str)
        domain = url.hostname
        if url.scheme == "":
            domain = url.path
        if not domain:
            self.metrics.invalid_domains += 1
            return
        self.metrics.total_urls += 1
        if self.config.cache_enabled:
            result = self._resolve_with_cache(domain)
        else:
            result = self._resolve_ip(domain)

        match result:
            case SuccessResult(resolved_ip) if resolved_ip:
                self._add_resolve_infos_to_event(event, rule, resolved_ip)
            case FailedResult(_, error) if error:
                self._handle_warning_error(event, rule, error)

    def _resolve_with_timeout_check(self, domain: str) -> SuccessResult | FailedResult:
        hash_string = self._hasher.hash_str(domain, salt=self.config.hash_salt)
        if self._timeout_cache.is_cached(hash_string):
            self.metrics.timeouts_cached += 1
            return FailedResult(FailureType.TIMEOUT)

        result = self._resolve_ip(domain)
        if isinstance(result, FailedResult) and self._is_timeout(result):
            self._timeout_cache.add(hash_string)
        return result

    def _resolve_with_cache(self, domain: str) -> SuccessResult | FailedResult:
        hash_string = self._hasher.hash_str(domain, salt=self.config.hash_salt)

        if self._domain_cache.is_cached(hash_string):
            self._domain_cache.update_cache(hash_string)
            result = self._domain_ip_map[hash_string]
            self.metrics.resolved_cached += 1
            return result

        result = self._resolve_with_timeout_check(domain)
        match result:
            case SuccessResult(_):
                self._domain_cache.add(hash_string)
                self._domain_ip_map.update({hash_string: result})
            case FailedResult(_) if not self._is_timeout(result):
                self._domain_cache.add(hash_string)
                self._domain_ip_map.update({hash_string: result})
        self.metrics.resolved_new += 1
        return result

    @staticmethod
    def _is_timeout(failed_result: FailedResult) -> bool:
        return failed_result.failure_type in (FailureType.TIMEOUT, FailureType.NO_NAMESERVERS)

    def _add_resolve_infos_to_event(self, event: dict, rule, resolved_ip: str):
        if resolved_ip:
            self._write_target_field(event, rule, resolved_ip)

    def _resolve_ip(self, domain: str) -> SuccessResult | FailedResult:
        """Resolve domain with timeout.

        Assumes socket default timeout is None and relies on threading to create a timeout.
        """
        try:
            result = self._dns_resolver.resolve(domain, "A")
            self.metrics.resolved_domains += 1
            return SuccessResult(result[0].address)
        except (FormError, DNSSyntaxError, TooBig):
            self.metrics.invalid_domains += 1
            return FailedResult(FailureType.INVALID)
        except (Timeout, LifetimeTimeout):
            self.metrics.timeouts += 1
            return FailedResult(FailureType.TIMEOUT)
        except NXDOMAIN:
            self.metrics.unknown_domains += 1
            return FailedResult(FailureType.UNKNOWN)
        except NoAnswer:
            return FailedResult(FailureType.NO_ANSWER)
        except NoNameservers as error:
            return FailedResult(FailureType.NO_NAMESERVERS, error)

    def _prune_domain_ip_map(self):
        if self._domain_ip_map_prune_timer.finished():
            self._domain_ip_map_prune_timer.reset()
            removed_keys = set(self._domain_ip_map.keys()).difference(self._domain_cache.keys())
            for hash_Str in removed_keys:
                self._domain_ip_map.pop(hash_Str)
