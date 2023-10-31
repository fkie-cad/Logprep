"""
Pseudonymizer
=============

The `pseudonymizer` is a processor that pseudonymizes certain fields of log messages to ensure
privacy regulations can be adhered to.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - pseudonymizername:
        type: pseudonymizer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        outputs:
            - kafka: pseudonyms_topic
        pubkey_analyst: /path/to/analyst_pubkey.pem
        pubkey_depseudo: /path/to/depseudo_pubkey.pem
        hash_salt: secret_salt
        regex_mapping: /path/to/regex_mapping.json
        max_cached_pseudonyms: 1000000
        max_caching_days: 1
        tld_lists:
            -/path/to/tld_list.dat

.. autoclass:: logprep.processor.pseudonymizer.processor.Pseudonymizer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.pseudonymizer.rule
"""
import datetime
import re
from functools import cached_property, lru_cache
from itertools import chain
from logging import Logger
from typing import List, Optional, Pattern
from urllib.parse import parse_qs, urlparse

from attrs import define, field, validators
from tldextract import TLDExtract
from urlextract import URLExtract

from logprep.abc.processor import Processor
from logprep.metrics.metrics import CounterMetric
from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.processor.pseudonymizer.rule import PseudonymizerRule
from logprep.util.cache import Cache
from logprep.util.getter import GetterFactory
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import list_of_urls_validator


class Pseudonymizer(Processor):
    """Pseudonymize log events to conform to EU privacy laws."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Pseudonymizer config"""

        outputs: tuple[dict[str, str]] = field(
            validator=[
                validators.deep_iterable(
                    member_validator=[
                        validators.instance_of(dict),
                        validators.deep_mapping(
                            key_validator=validators.instance_of(str),
                            value_validator=validators.instance_of(str),
                            mapping_validator=validators.max_len(1),
                        ),
                    ],
                    iterable_validator=validators.instance_of(tuple),
                ),
                validators.min_len(1),
            ],
            converter=tuple,
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""

        pubkey_analyst: str = field(validator=validators.instance_of(str))
        """
        Path to the public key of an analyst. For string format see :ref:`getters`.

        * /var/git/analyst_pub.pem"""
        pubkey_depseudo: str = field(validator=validators.instance_of(str))
        """
        Path to the public key for depseudonymization. For string format see :ref:`getters`.

        * /var/git/depseudo_pub.pem
        """
        hash_salt: str = field(validator=validators.instance_of(str))
        """A salt that is used for hashing."""
        regex_mapping: str = field(validator=validators.instance_of(str))
        """
        Path to a file (for string format see :ref:`getters`) with a regex mapping for
        pseudonymization, i.e.:

        * /var/git/logprep-rules/pseudonymizer_rules/regex_mapping.json
        """
        max_cached_pseudonyms: int = field(
            validator=[validators.instance_of(int), validators.gt(0)]
        )
        """
        The maximum number of cached pseudonyms. One cache entry requires ~250 Byte, thus 10
        million elements would require about 2.3 GB RAM. The cache is not persisted. Restarting
        Logprep does therefore clear the cache.
        This caching reduces the CPU load of Logprep (no demanding encryption must be performed
        repeatedly) and the load on subsequent components (i.e. Logstash or Elasticsearch).
        Setting. In case the cache size has been exceeded, the least recently used
        entry is deleteted. Has to be greater than 0.
        """
        tld_lists: Optional[list] = field(default=None, validator=[list_of_urls_validator])
        """Optional list of path to files with top-level domain lists
        (like https://publicsuffix.org/list/public_suffix_list.dat). If no path is given,
        a default list will be retrieved online and cached in a local directory. For local
        files the path has to be given with :code:`file:///path/to/file.dat`."""

    @define(kw_only=True)
    class Metrics(Processor.Metrics):
        """Tracks statistics about the Pseudonymizer"""

        pseudonymized_urls: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of urls that were pseudonymized",
                name="pseudonymizer_pseudonymized_urls",
            )
        )
        """Number urls that were pseudonymized"""

        new_results: int = 0
        """Number of new pseudodonyms"""
        cached_results: int = 0
        """Number of resolved from cache pseudonyms"""
        num_cache_entries: int = 0
        """Number of pseudonyms in cache"""
        cache_load: int = 0
        """cache usage """

    __slots__ = [
        "pseudonyms",
    ]

    pseudonyms: list

    HASH_PREFIX = "<pseudonym:"
    HASH_SUFFIX = ">"

    URL_SPLIT_PATTERN = re.compile("(://)")

    rule_class = PseudonymizerRule

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
    def _encrypter(self) -> DualPKCS1HybridEncrypter:
        _encrypter = DualPKCS1HybridEncrypter()
        _encrypter.load_public_keys(self._config.pubkey_analyst, self._config.pubkey_depseudo)
        return _encrypter

    @cached_property
    def _tld_extractor(self) -> TLDExtract:
        if self._config.tld_lists is not None:
            return TLDExtract(suffix_list_urls=self._config.tld_lists)
        else:
            return TLDExtract()

    @cached_property
    def _regex_mapping(self) -> dict:
        return GetterFactory.from_string(self._config.regex_mapping).get_yaml()

    @cached_property
    def _get_pseudonym_dict_cached(self):
        return lru_cache(maxsize=self._config.max_cached_pseudonyms)(self._get_pseudonym_dict)

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.metrics = self.PseudonymizerMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self.pseudonyms = []

    def setup(self):
        super().setup()
        # delete cache to avoid caching pseudonyms from previous runs
        if "_cache" in self.__dict__:
            del self.__dict__["_cache"]

    def load_rules(self, specific_rules_targets: List[str], generic_rules_targets: List[str]):
        super().load_rules(specific_rules_targets, generic_rules_targets)
        self._replace_regex_keywords_by_regex_expression()

    def process(self, event: dict):
        self.pseudonyms = []
        super().process(event)
        return (self.pseudonyms, self._config.outputs) if self.pseudonyms != [] else None

    def _apply_rules(self, event: dict, rule: PseudonymizerRule):
        for dotted_field, regex in rule.pseudonyms.items():
            field_value = get_dotted_field_value(event, dotted_field)
            if field_value is None:
                continue
            if isinstance(field_value, list):
                field_value = [
                    self._pseudonymize_string_field(rule, dotted_field, regex, str(value))
                    for value in field_value
                ]
            else:
                field_value = self._pseudonymize_string_field(
                    rule, dotted_field, regex, field_value
                )
            _ = add_field_to(event, dotted_field, field_value, overwrite_output_field=True)
        if "@timestamp" in event:
            for pseudonym in self.pseudonyms:
                pseudonym["@timestamp"] = event["@timestamp"]
        self._update_cache_metrics()

    def _pseudonymize_string_field(
        self, rule: PseudonymizerRule, dotted_field: str, regex: Pattern, field_value: str
    ) -> str:
        if regex.groups <= 1:
            clear_values = tuple(value for value in regex.findall(field_value) if value)
        if regex.groups > 1:
            clear_values = tuple(chain(*[value for value in regex.findall(field_value) if value]))
        if clear_values and dotted_field in rule.url_fields:
            field_value = self._get_field_with_pseudonymized_urls(field_value)
        pseudonymized_values = [self._pseudonymize_string(value) for value in clear_values]
        pseudonymize = zip(clear_values, pseudonymized_values)
        for clear_value, pseudonymized_value in pseudonymize:
            if clear_value:
                field_value = re.sub(re.escape(clear_value), pseudonymized_value, field_value)
        return field_value

    def _pseudonymize_string(self, value: str) -> str:
        pseudonym_dict = self._get_pseudonym_dict_cached(value)
        self.pseudonyms.append(pseudonym_dict)
        return self._wrap_hash(pseudonym_dict["pseudonym"])

    def _get_pseudonym_dict(self, value):
        hash_string = self._hasher.hash_str(value, salt=self._config.hash_salt)
        encrypted_origin = self._encrypter.encrypt(value)
        return {"pseudonym": hash_string, "origin": encrypted_origin}

    def _get_field_with_pseudonymized_urls(self, field_: str) -> str:
        for url_string in self._url_extractor.gen_urls(field_):
            url_parts = self._parse_url_parts(url_string)
            pseudonym_map = self._get_pseudonym_map(url_parts)
            url_split = self.URL_SPLIT_PATTERN.split(url_string)

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

    @lru_cache(maxsize=10000)
    def _parse_url_parts(self, url_str: str) -> dict:
        url = self._tld_extractor(url_str)
        if url_str.startswith("http://") or url_str.startswith("https://"):
            parsed_url = urlparse(url_str)
        else:
            parsed_url = urlparse("http://" + url_str)
        parts = {
            **{field: getattr(url, field) for field in url._fields},
            **{field: getattr(parsed_url, field) for field in parsed_url._fields},
            "auth": f"{parsed_url.username}:{parsed_url.password}" if parsed_url.username else None,
        }
        return parts

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

    def _get_pseudonym_map(self, url: dict) -> dict:
        pseudonym_map = {}
        if url.get("subdomain"):
            pseudonym_map[url["subdomain"]] = self._pseudonymize_string(url["subdomain"])
        if url.get("fragment"):
            pseudonym_map[url["fragment"]] = self._pseudonymize_string(url["fragment"])
        if url.get("auth"):
            pseudonym_map[url["auth"]] = self._pseudonymize_string(url["auth"])
        query_parts = parse_qs(url["query"])
        for values in query_parts.values():
            for value in values:
                if value:
                    pseudonym_map[value] = self._pseudonymize_string(value)
        if url.get("path"):
            if url["path"][1:]:
                pseudonym_map[url["path"][1:]] = self._pseudonymize_string(url["path"][1:])
        return pseudonym_map

    def _replace_regex_keywords_by_regex_expression(self):
        for rule in self._specific_rules:
            for dotted_field, regex_keyword in rule.pseudonyms.items():
                if regex_keyword in self._regex_mapping:
                    rule.pseudonyms[dotted_field] = re.compile(self._regex_mapping[regex_keyword])
        for rule in self._generic_rules:
            for dotted_field, regex_keyword in rule.pseudonyms.items():
                if regex_keyword in self._regex_mapping:
                    rule.pseudonyms[dotted_field] = re.compile(self._regex_mapping[regex_keyword])

    def _wrap_hash(self, hash_string: str) -> str:
        return self.HASH_PREFIX + hash_string + self.HASH_SUFFIX

    def _update_cache_metrics(self):
        cache_info = self._get_pseudonym_dict_cached.cache_info()
        self.metrics.new_results = cache_info.misses
        self.metrics.cached_results = cache_info.hits
        self.metrics.num_cache_entries = cache_info.currsize
        self.metrics.cache_load = cache_info.currsize / cache_info.maxsize
