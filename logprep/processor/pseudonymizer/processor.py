"""
Pseudonymizer
-------------

The `pseudonymizer` is a processor that pseudonymizes certain fields of log messages to ensure
privacy regulations can be adhered to.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - pseudonymizername:
        type: pseudonymizer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        pseudonyms_topic: pseudonyms_topic
        pubkey_analyst: /path/to/analyst_pubkey.pem
        pubkey_depseudo: /path/to/depseudo_pubkey.pem
        hash_salt: secret_salt
        regex_mapping: /path/to/regex_mapping.json
        max_cached_pseudonyms: 1000000
        max_caching_days: 1
        tld_lists:
            -/path/to/tld_list.dat
"""
import datetime
import re
import sys
from logging import Logger
from typing import Any, List, Optional, Tuple, Union
from urllib.parse import parse_qs

from attr import define, field, validators
from ruamel.yaml import YAML
from tldextract import TLDExtract
from urlextract import URLExtract

from logprep.abc import Processor
from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.processor.pseudonymizer.rule import PseudonymizeRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.validators import file_validator, list_of_urls_validator

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property

yaml = YAML(typ="safe", pure=True)


class Pseudonymizer(Processor):
    """Pseudonymize log events to conform to EU privacy laws."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Pseudonymizer config"""

        pseudonyms_topic: str = field(validator=validators.instance_of(str))
        """
        A Kafka-topic for pseudonyms.
        These are not the pseudonymized events, but just the pseudonyms with the encrypted real
        values.
        """
        pubkey_analyst: str = field(validator=file_validator)
        """
        Path to the public key of an analyst.

        * /var/git/analyst_pub.pem"""
        pubkey_depseudo: str = field(validator=file_validator)
        """
        Path to the public key for depseudonymization

        * /var/git/depseudo_pub.pem
        """
        hash_salt: str = field(validator=validators.instance_of(str))
        """A salt that is used for hashing."""
        regex_mapping: str = field(validator=file_validator)
        """
        Path to a file with a regex mapping for pseudonymization, i.e.:

        * /var/git/logprep-rules/pseudonymizer_rules/regex_mapping.json
        """
        max_cached_pseudonyms: int = field(validator=validators.instance_of(int))
        """
        The maximum number of cached pseudonyms. One cache entry requires ~250 Byte, thus 10
        million elements would require about 2.3 GB RAM. The cache is not persisted. Restarting
        Logprep does therefore clear the cache.
        """
        max_caching_days: int = field(validator=validators.instance_of(int))
        """
        Number of days a pseudonym is cached after the last time it appeared.
        This caching reduces the CPU load of Logprep (no demanding encryption must be performed
        repeatedly) and the load on subsequent components (i.e. Logstash or Elasticsearch).
        Setting the caching days to Null deactivates the caching. In case the cache size has been
        exceeded (see max_cached_pseudonyms), the oldest cached pseudonyms will be discarded first.
        Thus, it is possible that a pseudonym is re-added to the cache before max_caching_days has
        elapsed if it was discarded due to the size limit.
        """
        tld_lists: Optional[list] = field(default=None, validator=[list_of_urls_validator])
        """Optional list of path to files with top-level domain lists
        (like https://publicsuffix.org/list/public_suffix_list.dat). If no path is given,
        a default list will be retrieved online and cached in a local directory. For local
        files the path has to be given with :code:`file:///path/to/file.dat`."""

    @define(kw_only=True)
    class PseudonymizerMetrics(Processor.ProcessorMetrics):
        """Tracks statistics about the Pseudonymizer"""

        pseudonymized_urls: int = 0
        """Number urls that were pseudonymized"""

    __slots__ = [
        "_regex_mapping",
        "_cache",
        "pseudonyms",
        "pseudonymized_fields",
        "_tld_extractor",
    ]

    _regex_mapping: dict
    _cache: Cache
    _tld_lists: List[str]

    pseudonyms: list
    pseudonymized_fields: set

    HASH_PREFIX = "<pseudonym:"
    HASH_SUFFIX = ">"

    rule_class = PseudonymizeRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.metrics = self.PseudonymizerMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self._regex_mapping = {}
        self._cache = None
        self.pseudonyms = []
        self.pseudonymized_fields = set()
        self.setup()
        self._replace_regex_keywords_by_regex_expression()

    @cached_property
    def _url_extractor(self):
        return URLExtract()

    @cached_property
    def _cache_max_timedelta(self):
        return datetime.timedelta(days=self._config.max_caching_days)

    @cached_property
    def _hasher(self):
        return SHA256Hasher()

    @cached_property
    def _encrypter(self):
        return DualPKCS1HybridEncrypter()

    def setup(self):
        self._encrypter.load_public_keys(self._config.pubkey_analyst, self._config.pubkey_depseudo)
        self._cache = Cache(
            max_items=self._config.max_cached_pseudonyms, max_timedelta=self._cache_max_timedelta
        )
        self._init_tld_extractor()
        self._load_regex_mapping(self._config.regex_mapping)

    def _init_tld_extractor(self):
        if self._config.tld_lists is not None:
            self._tld_extractor = TLDExtract(suffix_list_urls=self._config.tld_lists)
        else:
            self._tld_extractor = TLDExtract()

    def _load_regex_mapping(self, regex_mapping_path: str):
        with open(regex_mapping_path, "r", encoding="utf8") as file:
            self._regex_mapping = yaml.load(file)

    def process(self, event: dict):
        self.pseudonymized_fields = set()
        self.pseudonyms = []
        super().process(event)
        return (self.pseudonyms, self._config.pseudonyms_topic) if self.pseudonyms != [] else None

    def _apply_rules(self, event: dict, rule: PseudonymizeRule):
        for dotted_field, regex in rule.pseudonyms.items():
            if dotted_field not in self.pseudonymized_fields:
                try:
                    dict_, key = self._innermost_field(dotted_field, event)
                    pre_pseudonymization_value = dict_[key]
                    dict_[key], new_pseudonyms, is_match = self._pseudonymize_field(
                        regex, str(dict_[key])
                    )
                    if is_match and dotted_field in rule.url_fields:
                        dict_[key] = self._get_field_with_pseudonymized_urls(
                            dict_[key], new_pseudonyms
                        )
                    if pre_pseudonymization_value != dict_[key]:
                        self.pseudonymized_fields.add(dotted_field)
                except KeyError:
                    pass
                else:
                    if new_pseudonyms is not None:
                        self.pseudonyms += new_pseudonyms

        if "@timestamp" in event:
            for pseudonym in self.pseudonyms:
                pseudonym["@timestamp"] = event["@timestamp"]

    @staticmethod
    def _innermost_field(dotted_field: str, event: dict) -> Tuple[Union[dict, Any], str]:
        keys = dotted_field.split(".")
        for i in range(len(keys) - 1):
            event = event[keys[i]]
        return event, keys[-1]

    def _pseudonymize_field(self, pattern: str, field_: str) -> Tuple[str, Optional[list], bool]:
        matches = re.match(pattern, field_)

        # No matches, no change
        if matches is None:
            return field_, None, False

        new_pseudonyms = []

        # Replace capture groups if there are any, else pseudonymize whole match (group(0))
        if any(matches.groups()):
            field_ = self._get_field_with_pseudonymized_capture_groups(matches, new_pseudonyms)

        return field_, new_pseudonyms if new_pseudonyms else None, True

    def _get_field_with_pseudonymized_capture_groups(self, matches, pseudonyms: List[dict]) -> str:
        field_ = ""
        unprocessed = matches.group(0)
        for capture_group in matches.groups():
            if capture_group:
                pseudonym = self._pseudonymize_value(capture_group, pseudonyms)
                processed, unprocessed = self._process_field(capture_group, unprocessed)
                field_ += processed + pseudonym
        field_ += unprocessed
        return field_

    def _get_field_with_pseudonymized_urls(self, field_: str, pseudonyms: List[dict]) -> str:
        pseudonyms = pseudonyms if pseudonyms else []
        for url_string in self._url_extractor.gen_urls(field_):
            url_parts = self._parse_url_parts(self._tld_extractor, url_string)
            pseudonym_map = self._get_pseudonym_map(pseudonyms, url_parts)
            url_split = re.split("(://)", url_string)

            replacements = self._get_parts_to_replace_in_correct_order(pseudonym_map)

            do_not_replace_pattern = (
                rf"(<pseudonym:[a-z0-9]*>|\?\w+=|&\w+=|"
                rf"{url_parts['domain']}\.{url_parts['suffix']})"
            )

            for replacement in replacements:
                parts_to_replace = re.split(do_not_replace_pattern, url_split[-1])
                for index, _ in enumerate(parts_to_replace):
                    if not re.findall(do_not_replace_pattern, parts_to_replace[index]):
                        parts_to_replace[index] = parts_to_replace[index].replace(
                            replacement, pseudonym_map[replacement]
                        )
                url_split[-1] = "".join(parts_to_replace)

            pseudonymized_url = "".join(url_split)
            field_ = field_.replace(url_string, pseudonymized_url)

            self.metrics.pseudonymized_urls += 1

        return field_

    def _parse_url_parts(self, tld_extractor: TLDExtract, url_str: str) -> dict:
        url = tld_extractor(url_str)

        parts = {}
        parts["scheme"] = self._find_first(r"^([a-z0-9]+)\:\/\/", url_str)
        parts["auth"] = self._find_first(r"(?:.*\/\/|^)(.*:.*)@.*", url_str)
        parts["domain"] = url.domain
        parts["subdomain"] = url.subdomain
        parts["suffix"] = url.suffix
        url_list = ".".join(list(url))
        parts["path"] = self._find_first(
            rf"(?:^[a-z0-9]+\:\/\/)?{url_list}(?:\:\d+)?([^#^\?]*).*", url_str
        )
        parts["query"] = self._find_first(r".*(\?\w+=[a-zA-Z0-9](?:&\w+=[a-zA-Z0-9]+)*).*", url_str)
        parts["fragment"] = self._find_first(r".*#(.*)", url_str)

        return parts

    @staticmethod
    def _find_first(pattern: str, string: str) -> Optional[str]:
        match = re.findall(pattern, string)
        if match:
            return match[0]
        return None

    @staticmethod
    def _get_parts_to_replace_in_correct_order(pseudonym_map: dict) -> List[str]:
        replacements = []
        keys = list(pseudonym_map.keys())
        for key in keys:
            if not replacements:
                replacements.append(key)
            else:
                for index in reversed(range(len(replacements))):
                    if not any(key in replacement for replacement in replacements[:index]):
                        replacements.insert(index + 1, key)
                        break
        replacements.reverse()
        return replacements

    def _get_pseudonym_map(self, pseudonyms: List[dict], url: dict) -> dict:
        pseudonym_map = {}
        if url.get("subdomain"):
            pseudonym_map[url["subdomain"]] = self._pseudonymize_value(url["subdomain"], pseudonyms)
        if url.get("fragment"):
            pseudonym_map[url["fragment"]] = self._pseudonymize_value(url["fragment"], pseudonyms)
        if url.get("auth"):
            pseudonym_map[url["auth"]] = self._pseudonymize_value(url["auth"], pseudonyms)
        query_parts = parse_qs(url["query"])
        for values in query_parts.values():
            for value in values:
                if value:
                    pseudonym_map[value] = self._pseudonymize_value(value, pseudonyms)
        if url.get("path"):
            if url["path"][1:]:
                pseudonym_map[url["path"][1:]] = self._pseudonymize_value(
                    url["path"][1:], pseudonyms
                )
        return pseudonym_map

    @staticmethod
    def _process_field(capture_group: str, unprocessed: str) -> Tuple[str, str]:
        split_by_cap_group = unprocessed.split(capture_group, 1)
        processed_but_not_pseudonymized = split_by_cap_group[0]
        unprocessed = split_by_cap_group[-1]
        return processed_but_not_pseudonymized, unprocessed

    def _pseudonymize_value(self, value: str, pseudonyms: List[dict]) -> str:
        hash_string = self._hasher.hash_str(value, salt=self._config.hash_salt)
        if self._cache.requires_storing(hash_string):
            encrypted_origin = self._encrypter.encrypt(value)
            pseudonyms.append({"pseudonym": hash_string, "origin": encrypted_origin})
        return self._wrap_hash(hash_string)

    def _replace_regex_keywords_by_regex_expression(self):
        for rule in self._specific_rules:
            for dotted_field, regex_keyword in rule.pseudonyms.items():
                rule.pseudonyms[dotted_field] = self._regex_mapping[regex_keyword]
        for rule in self._generic_rules:
            for dotted_field, regex_keyword in rule.pseudonyms.items():
                rule.pseudonyms[dotted_field] = self._regex_mapping[regex_keyword]

    def _wrap_hash(self, hash_string: str) -> str:
        return self.HASH_PREFIX + hash_string + self.HASH_SUFFIX
