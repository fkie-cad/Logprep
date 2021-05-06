"""This module contains a Pseudonymizer that must be used to conform to EU privacy laws."""

from typing import List, Tuple, Union, Any, Optional
from logging import Logger

import re
from ruamel.yaml import safe_load
from time import time
import datetime
from multiprocessing import current_process

from urlextract import URLExtract
from tldextract import TLDExtract
from urllib.parse import parse_qs

from logprep.processor.base.processor import RuleBasedProcessor

from logprep.util.cache import Cache
from logprep.util.hasher import SHA256Hasher
from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.processor.pseudonymizer.rule import PseudonymizerRule

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class Pseudonymizer(RuleBasedProcessor):
    """Pseudonymize log events to conform to EU privacy laws."""

    HASH_PREFIX = "<pseudonym:"
    HASH_SUFFIX = ">"

    def __init__(self, name: str, pubkey_analyst: str, pubkey_depseudo: str, hash_salt: str,
                 pseudonyms_topic: str, regex_mapping_path: str, cache_max_items: int,
                 cache_max_timedelta: datetime.timedelta, tld_list: str, logger: Logger):
        self._logger = logger
        self._name = name
        self._description = self.describe()
        self.ps = ProcessorStats()

        self._pubkey_analyst = pubkey_analyst
        self._pubkey_depseudo = pubkey_depseudo
        self._hash_salt = hash_salt
        self._hasher = SHA256Hasher()
        self._encrypter = DualPKCS1HybridEncrypter()

        self._pseudonyms_topic = pseudonyms_topic
        self._processed_count = 0

        self._regex_mapping_path = regex_mapping_path
        self._regex_mapping = dict()

        self._specific_rules = []
        self._generic_rules = []

        self._cache_max_items = cache_max_items
        self._cache_max_timedelta = cache_max_timedelta
        self._cache = None

        self._tld_list = tld_list
        self._url_extractor = URLExtract()
        self._tld_extractor = None

    def setup(self):
        self._description = self.describe()
        self._encrypter.load_public_keys(self._pubkey_analyst, self._pubkey_depseudo)
        self._cache = Cache(max_items=self._cache_max_items, max_timedelta=self._cache_max_timedelta)
        self._tld_extractor = TLDExtract(suffix_list_urls=[self._tld_list])
        self._load_regex_mapping(self._regex_mapping_path)

    def _load_regex_mapping(self, regex_mapping_path: str):
        with open(regex_mapping_path, 'r') as file:
            self._regex_mapping = safe_load(file)

    def add_rules_from_directory(self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]):
        for specific_rules_dir in specific_rules_dirs:
            if specific_rules_dir:
                self._specific_rules = self._get_rules_from_directory(specific_rules_dir)
        for generic_rules_dir in generic_rules_dirs:
            if generic_rules_dir:
                self._generic_rules = self._get_rules_from_directory(generic_rules_dir)

        self.ps.setup_rules(self._specific_rules + self._generic_rules)
        self._logger.debug('{} loaded {} specific rules ({})'.format(self.describe(),
                                                                     len(self._specific_rules),
                                                                     current_process().name))
        self._logger.debug(
            '{} loaded {} generic rules ({})'.format(self.describe(), len(self._generic_rules),
                                                     current_process().name))

    def describe(self) -> str:
        return f'Pseudonymizer ({self._name})'

    @TimeMeasurement.measure_time('pseudonymizer')
    def process(self, event: dict) -> Optional[tuple]:
        pseudonyms = self._pseudonymize_event(event)
        if '@timestamp' in event:
            for pseudonym in pseudonyms:
                pseudonym['@timestamp'] = event['@timestamp']
        self._processed_count += 1
        self.ps.update_processed_count(self._processed_count)

        return (pseudonyms, self._pseudonyms_topic) if pseudonyms != [] else None

    def events_processed_count(self) -> int:
        return self._processed_count

    def shut_down(self):
        pass

    def _get_rules_from_directory(self, rule_directory: str) -> List[PseudonymizerRule]:
        rules = []
        rule_paths = self._list_json_files_in_directory(rule_directory)
        for rule_path in rule_paths:
            rules_raw = PseudonymizerRule.create_rules_from_file(rule_path)
            for rule in rules_raw:
                self._replace_regex_keywords_by_regex_expression(rule)
                rules.append(rule)
        return rules

    def _pseudonymize_event(self, event: dict) -> list:
        """Pseudonymize a log event and return all pseudonyms."""
        pseudonyms = []
        pseudonymized_fields = set()

        for idx, rule in enumerate(self._specific_rules):
            begin = time()
            if rule.matches(event):
                self._logger.debug('{} processing specific matching event'.format(self._description))
                self._apply_rule(rule, event, pseudonymized_fields, pseudonyms)

                processing_time = float('{:.10f}'.format(time() - begin))
                self.ps.update_per_rule(idx, processing_time, rule)
                break

        for idx, rule in enumerate(self._generic_rules):
            begin = time()
            if rule.matches(event):
                self._logger.debug('{} processing generic matching event'.format(self._description))
                processing_time = float('{:.10f}'.format(time() - begin))
                self.ps.update_per_rule(idx, processing_time, rule)

                self._apply_rule(rule, event, pseudonymized_fields, pseudonyms)

        return pseudonyms

    def _apply_rule(self, rule: PseudonymizerRule, event: dict, pseudonymized_fields: set,
                    pseudonyms: list):
        for dotted_field, regex in rule.pseudonyms.items():
            if dotted_field not in pseudonymized_fields:
                try:
                    dict_, key = self._innermost_field(dotted_field, event)
                    pre_pseudonymization_value = dict_[key]
                    dict_[key], new_pseudonyms, is_match = self._pseudonymize_field(regex, str(dict_[key]))
                    if is_match and dotted_field in rule.url_fields:
                        dict_[key] = self._get_field_with_pseudonymized_urls(dict_[key], new_pseudonyms)
                    if pre_pseudonymization_value != dict_[key]:
                        pseudonymized_fields.add(dotted_field)
                except KeyError:
                    pass
                else:
                    if new_pseudonyms is not None:
                        pseudonyms += new_pseudonyms

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
        field = ''
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
            url_split = re.split('(://)', url_string)

            replacements = self._get_parts_to_replace_in_correct_order(pseudonym_map)

            do_not_replace_pattern = r'(<pseudonym:[a-z0-9]*>|\?\w+=|&\w+=|{}\.{})'.format(url_parts['domain'],
                                                                                           url_parts['suffix'])
            for replacement in replacements:
                parts_to_replace = re.split(do_not_replace_pattern, url_split[-1])
                for x in range(len(parts_to_replace)):
                    if not re.findall(do_not_replace_pattern, parts_to_replace[x]):
                        parts_to_replace[x] = parts_to_replace[x].replace(replacement, pseudonym_map[replacement])
                url_split[-1] = ''.join(parts_to_replace)

            pseudonymized_url = ''.join(url_split)
            field = field.replace(url_string, pseudonymized_url)

            self.ps.increment_aggregation('urls')

        return field

    def _parse_url_parts(self, tld_extractor: TLDExtract, url_str: str) -> dict:
        url = tld_extractor(url_str)

        parts = dict()
        parts['scheme'] = self._find_first(r'^([a-z0-9]+)\:\/\/', url_str)
        parts['auth'] = self._find_first(r'(?:.*\/\/|^)(.*:.*)@.*', url_str)
        parts['domain'] = url.domain
        parts['subdomain'] = url.subdomain
        parts['suffix'] = url.suffix
        parts['path'] = self._find_first(r'(?:^[a-z0-9]+\:\/\/)?{}(?:\:\d+)?([^#^\?]*).*'.format('.'.join(list(url))),
                                         url_str)
        parts['query'] = self._find_first(r'.*(\?\w+=[a-zA-Z0-9](?:&\w+=[a-zA-Z0-9]+)*).*', url_str)
        parts['fragment'] = self._find_first(r'.*#(.*)', url_str)

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
                for x in reversed(range(len(replacements))):
                    if not any([key in replacement for replacement in replacements[:x]]):
                        replacements.insert(x + 1, key)
                        break
        replacements.reverse()
        return replacements

    def _get_pseudonym_map(self, pseudonyms: List[dict], url: dict) -> dict:
        pseudonym_map = dict()
        if url.get('subdomain'):
            pseudonym_map[url['subdomain']] = self._pseudonymize_value(url['subdomain'], pseudonyms)
        if url.get('fragment'):
            pseudonym_map[url['fragment']] = self._pseudonymize_value(url['fragment'], pseudonyms)
        if url.get('auth'):
            pseudonym_map[url['auth']] = self._pseudonymize_value(url['auth'], pseudonyms)
        query_parts = parse_qs(url['query'])
        for values in query_parts.values():
            for value in values:
                if value:
                    pseudonym_map[value] = self._pseudonymize_value(value, pseudonyms)
        if url.get('path'):
            if url['path'][1:]:
                pseudonym_map[url['path'][1:]] = self._pseudonymize_value(url['path'][1:], pseudonyms)
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

    def _replace_regex_keywords_by_regex_expression(self, rule: PseudonymizerRule):
        for dotted_field, regex_keyword in rule.pseudonyms.items():
            rule.pseudonyms[dotted_field] = self._regex_mapping[regex_keyword]

    def _wrap_hash(self, hash_string: str) -> str:
        return self.HASH_PREFIX + hash_string + self.HASH_SUFFIX
