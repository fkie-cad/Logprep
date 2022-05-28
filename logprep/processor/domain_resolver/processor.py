"""This module contains functionality for resolving domains."""
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
        """domain_resolver config"""

        tld_list: str = field(validator=validators.instance_of(str))
        timeout: Optional[float] = field(
            default=0.5, validator=validators.optional(validators.instance_of(float))
        )
        max_cached_domains: int = field(validator=validators.instance_of(int))
        max_caching_days: int = field(validator=validators.instance_of(int))
        hash_salt: str = field(validator=validators.instance_of(str))
        cache_enabled: bool = field(
            default=True, validator=validators.optional(validator=validators.instance_of(bool))
        )
        debug_cache: bool = field(
            default=False, validator=validators.optional(validator=validators.instance_of(bool))
        )

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
