"""This module contains functionality for resolving domains."""
from time import time
from typing import List
from logging import Logger, DEBUG

import socket
from multiprocessing.pool import ThreadPool
from multiprocessing import context
from multiprocessing import current_process

from os import walk
from os.path import isdir, realpath, join

import datetime

from tldextract import TLDExtract

from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.processor.base.exceptions import (
    NotARulesDirectoryError,
    InvalidRuleDefinitionError,
    InvalidRuleFileError,
)

from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement
from logprep.util.helper import add_field_to


class DomainResolverError(BaseException):
    """Base class for DomainResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DomainResolver ({name}): {message}")


class DuplicationError(DomainResolverError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the DomainResolver: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class DomainResolver(RuleBasedProcessor):
    """Resolve domains."""

    def __init__(
        self,
        name: str,
        tree_config: str,
        tld_list: str,
        timeout: float,
        cache_max_items: int,
        cache_max_timedelta: datetime.timedelta,
        salt: str,
        cache_enabled: bool,
        debug_cache: bool,
        logger: Logger,
    ):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._timeout = timeout
        self._tld_extractor = TLDExtract(suffix_list_urls=[tld_list])
        self._thread_pool = ThreadPool(processes=1)

        self._hasher = SHA256Hasher()
        self._salt = salt
        self._cache = Cache(max_items=cache_max_items, max_timedelta=cache_max_timedelta)
        self._cache_enabled = cache_enabled
        self._debug_cache = debug_cache

        self._domain_ip_map = dict()

    # pylint: disable=arguments-differ
    def add_rules_from_directory(self, rule_paths: List[str]):
        """Add rules from given directory."""
        for path in rule_paths:
            if not isdir(realpath(path)):
                raise NotARulesDirectoryError(self._name, path)

            for root, _, files in walk(path):
                json_files = []
                for file in files:
                    if (file.endswith(".json") or file.endswith(".yml")) and not file.endswith(
                        "_test.json"
                    ):
                        json_files.append(file)
                for file in json_files:
                    rules = self._load_rules_from_file(join(root, file))
                    for rule in rules:
                        self._tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._tree.rule_counter} rules"
                f" ({current_process().name})"
            )

        self.ps.setup_rules([None] * self._tree.rule_counter)

    # pylint: enable=arguments-differ

    def _load_rules_from_file(self, path: str):
        try:
            return DomainResolverRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path) from error

    def describe(self) -> str:
        return f"DomainResolver ({self._name})"

    @TimeMeasurement.measure_time("domain_resolver")
    def process(self, event: dict):
        self._event = event

        for rule in self._tree.get_matching_rules(event):
            try:
                begin = time()
                self._apply_rules(event, rule)
                processing_time = float("{:.10f}".format(time() - begin))
                idx = self._tree.get_rule_id(rule)
                self.ps.update_per_rule(idx, processing_time)
            except DomainResolverError as error:
                raise ProcessingWarning(str(error)) from error

        self.ps.increment_processed_count()

    def _apply_rules(self, event, rule):
        domain_or_url = rule.source_url_or_domain
        # new variable: output field
        output_field = rule.output_field
        domain_or_url_str = self._get_dotted_field_value(event, domain_or_url)
        if domain_or_url_str:
            domain = self._tld_extractor(domain_or_url_str).fqdn
            if domain:
                self.ps.increment_nested(self._name, "total_urls")
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
                            self.ps.increment_nested(self._name, "resolved_new")

                        if self._debug_cache:
                            event["resolved_ip_debug"] = dict()
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
                                raise DuplicationError(self._name, [output_field])

                            self.ps.increment_nested(self._name, "resolved_cache")
                    except (context.TimeoutError, OSError):
                        self._domain_ip_map[hash_string] = None
                        self.ps.increment_nested(self._name, "timeouts")
                    except UnicodeError as error:
                        raise DomainResolverError(
                            self._name, f"{error} for domain '{domain}'"
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
                            raise DomainResolverError(self._name, error_msg) from error
