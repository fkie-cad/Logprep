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
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_field_to

if sys.version_info.minor < 8:
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class DomainResolverError(BaseException):
    """Base class for DomainResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DomainResolver ({name}): {message}")


class DomainResolver(Processor):
    """Resolve domains."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """DomainResolver config"""

        tld_list: str = field(validator=validators.instance_of(str))
        """Path to a file with a list of top-level domains
        (like https://publicsuffix.org/list/public_suffix_list.dat)."""
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

    __slots__ = ["_domain_ip_map"]
    if not sys.version_info.minor < 7:
        __slots__.append("__dict__")

    _domain_ip_map: dict

    rule_class = DomainResolverRule

    def __init__(
        self,
        name: str,
        configuration: Processor.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)

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
        tld_list = self._config.tld_list
        return TLDExtract(suffix_list_urls=[tld_list])

    @property
    def _timeout(self):
        return self._config.timeout

    def _apply_rules(self, event, rule):
        domain_or_url = rule.source_url_or_domain
        # new variable: output field
        output_field = rule.output_field
        domain_or_url_str = self._get_dotted_field_value(event, domain_or_url)
        if domain_or_url_str:
            domain = self._tld_extractor(domain_or_url_str).fqdn
            if domain:
                self.ps.increment_nested(self.name, "total_urls")
                if self._config.cache_enabled:
                    try:
                        hash_string = self._hasher.hash_str(domain, salt=self._config.hash_salt)
                        requires_storing = self._cache.requires_storing(hash_string)
                        if requires_storing:
                            result = self._thread_pool.apply_async(socket.gethostbyname, (domain,))
                            resolved_ip = result.get(timeout=self._config.timeout)
                            if len(self._domain_ip_map) >= len(self._cache):
                                first_hash = next(iter(self._cache.keys()))
                                del self._domain_ip_map[first_hash]
                            self._domain_ip_map[hash_string] = resolved_ip
                            self.ps.increment_nested(self.name, "resolved_new")

                        if self._config.debug_cache:
                            event["resolved_ip_debug"] = {}
                            event_dbg = event["resolved_ip_debug"]
                            if requires_storing:
                                event_dbg["obtained_from_cache"] = False
                            else:
                                event_dbg["obtained_from_cache"] = True
                            event_dbg["cache_size"] = len(self._domain_ip_map.keys())

                        if self._domain_ip_map[hash_string] is not None:
                            adding_was_successful = add_field_to(
                                event, output_field, self._domain_ip_map[hash_string]
                            )

                            if not adding_was_successful:
                                message = (
                                    f"DomainResolver ({self.name}): The following "
                                    f"fields already existed and "
                                    f"were not overwritten by the DomainResolver: "
                                    f"{output_field}"
                                )
                                raise ProcessingWarning(message=message)
                            self.ps.increment_nested(self.name, "resolved_cache")
                    except (context.TimeoutError, OSError):
                        self._domain_ip_map[hash_string] = None
                        self.ps.increment_nested(self.name, "timeouts")
                    except UnicodeError as error:
                        raise DomainResolverError(
                            self.name, f"{error} for domain '{domain}'"
                        ) from error
                else:
                    if output_field not in event:
                        try:
                            result = self._thread_pool.apply_async(socket.gethostbyname, (domain,))
                            event[output_field] = result.get(timeout=self._config.timeout)
                        except (context.TimeoutError, OSError):
                            pass
                        except UnicodeError as error:
                            error_msg = f"{error} for domain '{domain}'"
                            raise DomainResolverError(self.name, error_msg) from error
