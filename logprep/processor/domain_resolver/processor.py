"""This module contains functionality for resolving domains."""
import datetime
import socket
from logging import DEBUG, Logger
from multiprocessing import context, current_process
from multiprocessing.pool import ThreadPool
from typing import List

from tldextract import TLDExtract

from logprep.processor.base.exceptions import InvalidRuleDefinitionError, InvalidRuleFileError
from logprep.processor.base.processor import ProcessingWarning, RuleBasedProcessor
from logprep.processor.domain_resolver.rule import DomainResolverRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats


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
        configuration: dict,
        logger: Logger,
    ):
        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

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
        self._specific_rules_dirs = configuration.get("specific_rules")
        self._generic_rules_dirs = configuration.get("generic_rules")
        self.add_rules_from_directory(
            specific_rules_dirs=self._specific_rules_dirs,
            generic_rules_dirs=self._generic_rules_dirs,
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = DomainResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = DomainResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"generic rules ({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

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
