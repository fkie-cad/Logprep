"""
DomainResolver
--------------

The `domain_resolver` is a processor that can resolve domains inside a defined field.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - domainresolvername:
        type: domain_resolver
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        hyperscan_db_path: tmp/path/scan.db
        tld_list: tmp/path/tld.dat
        timeout: 0.5
        max_cached_domains: 20000
        max_caching_days: 1
        hash_salt: secure_salt
        cache_enabled: true
        debug_cache: false
"""
import datetime
import sys
import socket
from logging import Logger
from multiprocessing import context
from multiprocessing.pool import ThreadPool
from typing import Optional
from attr import define, field, validators

from tldextract import TLDExtract

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import list_of_urls_validator

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class DomainResolver(Processor):
    """Resolve domains."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """DomainResolver config"""

        tld_lists: Optional[list] = field(default=None, validator=[list_of_urls_validator])
        """Optional list of path to files with top-level domain lists
        (like https://publicsuffix.org/list/public_suffix_list.dat). If no path is given,
        a default list will be retrieved online and cached in a local directory. For local
        files the path has to be given with :code:`file:///path/to/file.dat`."""
        timeout: Optional[float] = field(
            default=0.5, validator=validators.optional(validators.instance_of(float))
        )
        """Timeout for resolving of domains."""
        max_cached_domains: int = field(validator=validators.instance_of(int))
        """The maximum number of cached domains. One cache entry requires ~250 Byte, thus 10
        million elements would require about 2.3 GB RAM. The cache is not persisted. Restarting
        Logprep does therefore clear the cache."""
        max_caching_days: int = field(validator=validators.instance_of(int))
        """Number of days a domains is cached after the last time it appeared.
        This caching reduces the CPU load of Logprep (no demanding encryption must be performed
        repeatedly) and the load on subsequent components (i.e. Logstash or Elasticsearch).
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
    class DomainResolverMetrics(Processor.ProcessorMetrics):
        """Tracks statistics about the DomainResolver"""

        total_urls: int = 0
        """Number of all resolved urls"""
        resolved_new: int = 0
        """Number of urls that had to be resolved newly"""
        resolved_cached: int = 0
        """Number of urls that were resolved from cache"""
        timeouts: int = 0
        """Number of timeouts that occurred while resolving a url"""

    __slots__ = ["_domain_ip_map"]

    _domain_ip_map: dict

    rule_class = DomainResolverRule

    def __init__(
        self,
        name: str,
        configuration: Processor.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.metrics = self.DomainResolverMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self._domain_ip_map = {}

    @cached_property
    def _cache(self):
        cache_max_timedelta = datetime.timedelta(days=self._config.max_caching_days)
        return Cache(max_items=self._config.max_cached_domains, max_timedelta=cache_max_timedelta)

    @cached_property
    def _hasher(self):
        return SHA256Hasher()

    @cached_property
    def _thread_pool(self):
        return ThreadPool(processes=1)

    @cached_property
    def _tld_extractor(self):
        if self._config.tld_lists is not None:
            return TLDExtract(suffix_list_urls=self._config.tld_lists)
        return TLDExtract()

    def _apply_rules(self, event, rule):
        source_field = rule.source_fields[0]
        target_field = rule.target_field
        overwrite_target = rule.overwrite_target
        domain_or_url_str = get_dotted_field_value(event, source_field)
        if not domain_or_url_str:
            return
        domain = self._tld_extractor(domain_or_url_str).fqdn
        if not domain:
            return
        self.metrics.total_urls += 1
        if self._config.cache_enabled:
            hash_string = self._hasher.hash_str(domain, salt=self._config.hash_salt)
            requires_storing = self._cache.requires_storing(hash_string)
            if requires_storing:
                resolved_ip = self._resolve_ip(domain, hash_string)
                self._domain_ip_map.update({hash_string: resolved_ip})
                self.metrics.resolved_new += 1
            else:
                resolved_ip = self._domain_ip_map.get(hash_string)
                self.metrics.resolved_cached += 1
            self._add_resolve_infos_to_event(event, target_field, resolved_ip, overwrite_target)
            if self._config.debug_cache:
                self._store_debug_infos(event, requires_storing)
        else:
            resolved_ip = self._resolve_ip(domain)
            self._add_resolve_infos_to_event(event, target_field, resolved_ip, overwrite_target)

    def _add_resolve_infos_to_event(self, event, output_field, resolved_ip, overwrite_target):
        if resolved_ip:
            adding_was_successful = add_field_to(
                event, output_field, resolved_ip, overwrite_output_field=overwrite_target
            )

            if not adding_was_successful:
                raise DuplicationError(self.name, [output_field])

    def _resolve_ip(self, domain, hash_string=None):
        try:
            result = self._thread_pool.apply_async(socket.gethostbyname, (domain,))
            resolved_ip = result.get(timeout=self._config.timeout)
            return resolved_ip
        except (context.TimeoutError, OSError):
            if hash_string:
                self._domain_ip_map[hash_string] = None
            self.metrics.timeouts += 1

    def _store_debug_infos(self, event, requires_storing):
        event["resolved_ip_debug"] = {}
        event_dbg = event["resolved_ip_debug"]
        if requires_storing:
            event_dbg["obtained_from_cache"] = False
        else:
            event_dbg["obtained_from_cache"] = True
        event_dbg["cache_size"] = len(self._domain_ip_map.keys())
