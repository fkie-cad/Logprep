"""This module contains functionality for resolving domains."""
import datetime
import socket
from logging import Logger
from multiprocessing import context
from multiprocessing.pool import ThreadPool
from async_timeout import timeout
from attr import define, field, validators

from tldextract import TLDExtract

from logprep.abc import Processor
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_field_to


class DomainResolverError(BaseException):
    """Base class for DomainResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DomainResolver ({name}): {message}")


class DomainResolver(Processor):
    """Resolve domains."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """domain_resolver config"""

        tld_list: str = field(validator=validators.instance_of(str))
        timeout: float = field(validator=validators.instance_of(float))
        max_cached_domains: int = field(validator=validators.instance_of(int))
        max_caching_days: int = field(validator=validators.instance_of(int))
        hash_salt: str = field(validator=validators.instance_of(str))

    __slots__ = [
        "_timeout",
        "_tld_extractor",
        "_thread_pool",
        "_hasher",
        "_salt",
        "_cache",
        "_cache_enabled",
        "_debug_cache",
        "_domain_ip_map",
    ]

    _domain_ip_map: dict

    _debug_cache: bool

    _cache_enabled: bool

    _cache: Cache

    _hasher: SHA256Hasher

    _salt: str

    _thread_pool: ThreadPool

    _tld_extractor: TLDExtract

    _timeout: str

    rule_class = DomainResolverRule

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)

        self._timeout = configuration.get("timeout", 0.5)
        tld_list = configuration.get("tld_list")
        self._tld_extractor = TLDExtract(suffix_list_urls=[tld_list])
        self._thread_pool = ThreadPool(processes=1)

        self._hasher = SHA256Hasher()
        self._salt = configuration.get("hash_salt")
        cache_max_items = configuration.get("max_cached_domains")
        cache_max_timedelta = datetime.timedelta(days=configuration["max_caching_days"])
        self._cache = Cache(max_items=cache_max_items, max_timedelta=cache_max_timedelta)
        self._cache_enabled = configuration.get("cache_enabled", True)
        self._debug_cache = configuration.get("debug_cache", False)

        self._domain_ip_map = {}

    def _apply_rules(self, event, rule):
        domain_or_url = rule.source_url_or_domain
        # new variable: output field
        output_field = rule.output_field
        domain_or_url_str = self._get_dotted_field_value(event, domain_or_url)
        if domain_or_url_str:
            domain = self._tld_extractor(domain_or_url_str).fqdn
            if domain:
                self.ps.increment_nested(self.name, "total_urls")
                if self._cache_enabled:
                    try:
                        hash_string = self._hasher.hash_str(domain, salt=self._salt)
                        requires_storing = self._cache.requires_storing(hash_string)
                        if requires_storing:
                            result = self._thread_pool.apply_async(socket.gethostbyname, (domain,))
                            resolved_ip = result.get(timeout=self._timeout)
                            if len(self._domain_ip_map) >= len(self._cache):
                                first_hash = next(iter(self._cache.keys()))
                                del self._domain_ip_map[first_hash]
                            self._domain_ip_map[hash_string] = resolved_ip
                            self.ps.increment_nested(self.name, "resolved_new")

                        if self._debug_cache:
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
                            event[output_field] = result.get(timeout=self._timeout)
                        except (context.TimeoutError, OSError):
                            pass
                        except UnicodeError as error:
                            error_msg = f"{error} for domain '{domain}'"
                            raise DomainResolverError(self.name, error_msg) from error
