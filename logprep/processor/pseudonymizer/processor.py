"""This module contains a Pseudonymizer that must be used to conform to EU privacy laws."""

import datetime
import re
from logging import Logger
from typing import Any, List, Optional, Tuple, Union
from urllib.parse import parse_qs

from ruamel.yaml import YAML
from tldextract import TLDExtract
from urlextract import URLExtract
from logprep.abc import Processor
from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.processor.pseudonymizer.rule import PseudonymizerRule
from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.util.processor_stats import ProcessorStats

yaml = YAML(typ="safe", pure=True)


class Pseudonymizer(Processor):
    """Pseudonymize log events to conform to EU privacy laws."""

    __slots__ = [
        "_pubkey_analyst",
        "_pubkey_depseudo",
        "_hash_salt",
        "_hasher",
        "_encrypter",
        "_pseudonyms_topic",
        "_regex_mapping_path",
        "_regex_mapping",
        "_cache_max_items",
        "_cache_max_timedelta",
        "_cache",
        "_tld_list",
        "_url_extractor",
        "pseudonyms",
        "pseudonymized_fields",
        "_tld_extractor",
    ]

    _regex_mapping: dict
    _regex_mapping_path: str
    _pseudonyms_topic: str
    _encrypter: DualPKCS1HybridEncrypter
    _hasher: SHA256Hasher
    _hash_salt: str
    _pubkey_analyst: str
    _pubkey_depseudo: str
    _cache_max_items: int
    _cache_max_timedelta: datetime.timedelta
    _cache: Cache
    _tld_list: str
    _url_extractor: URLExtract
    _tld_extractor: TLDExtract

    pseudonyms: list
    pseudonymized_fields: set

    HASH_PREFIX = "<pseudonym:"
    HASH_SUFFIX = ">"

    rule_class = PseudonymizerRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        self._pubkey_analyst = configuration.get("pubkey_analyst")
        self._pubkey_depseudo = configuration.get("pubkey_depseudo")
        self._hash_salt = configuration.get("hash_salt")
        self._hasher = SHA256Hasher()
        self._encrypter = DualPKCS1HybridEncrypter()

        self._pseudonyms_topic = configuration.get("pseudonyms_topic")

        self._regex_mapping_path = configuration.get("regex_mapping")
        self._regex_mapping = {}

        self._cache_max_items = configuration.get("max_cached_pseudonyms")
        self._cache_max_timedelta = datetime.timedelta(days=configuration.get("max_caching_days"))
        self._cache = None

        self._tld_list = configuration.get("tld_list")
        self._url_extractor = URLExtract()
        self.pseudonyms = []
        self.pseudonymized_fields = set()
        self.setup()
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._replace_regex_keywords_by_regex_expression()

    def setup(self):
        self._encrypter.load_public_keys(self._pubkey_analyst, self._pubkey_depseudo)
        self._cache = Cache(
            max_items=self._cache_max_items, max_timedelta=self._cache_max_timedelta
        )
        self._tld_extractor = TLDExtract(suffix_list_urls=[self._tld_list])
        self._load_regex_mapping(self._regex_mapping_path)

    def _load_regex_mapping(self, regex_mapping_path: str):
        with open(regex_mapping_path, "r", encoding="utf8") as file:
            self._regex_mapping = yaml.load(file)

    def process(self, event: dict):
        self.pseudonymized_fields = set()
        self.pseudonyms = []
        super().process(event)
        return (self.pseudonyms, self._pseudonyms_topic) if self.pseudonyms != [] else None

    def _apply_rules(self, event: dict, rule: PseudonymizerRule):
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

    def _pseudonymize_field(self, pattern: str, field: str) -> Tuple[str, Optional[list], bool]:
        matches = re.match(pattern, field)

        # No matches, no change
        if matches is None:
            return field, None, False

        new_pseudonyms = []

        # Replace capture groups if there are any, else pseudonymize whole match (group(0))
        if any(matches.groups()):
            field = self._get_field_with_pseudonymized_capture_groups(matches, new_pseudonyms)

        return field, new_pseudonyms if new_pseudonyms else None, True

    def _get_field_with_pseudonymized_capture_groups(self, matches, pseudonyms: List[dict]) -> str:
        field = ""
        unprocessed = matches.group(0)
        for capture_group in matches.groups():
            if capture_group:
                pseudonym = self._pseudonymize_value(capture_group, pseudonyms)
                processed, unprocessed = self._process_field(capture_group, unprocessed)
                field += processed + pseudonym
        field += unprocessed
        return field

    def _get_field_with_pseudonymized_urls(self, field: str, pseudonyms: List[dict]) -> str:
        pseudonyms = pseudonyms if pseudonyms else []
        for url_string in self._url_extractor.gen_urls(field):
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
            field = field.replace(url_string, pseudonymized_url)

            self.ps.increment_aggregation("urls")

        return field

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
                    if not any([key in replacement for replacement in replacements[:index]]):
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
        hash_string = self._hasher.hash_str(value, salt=self._hash_salt)
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
