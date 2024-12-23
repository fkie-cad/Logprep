"""
Pseudonymizer
=============

The :code:`pseudonymizer` is a processor that pseudonymizes certain fields of log messages to ensure
privacy regulations can be adhered to.

.. security-best-practice::
   :title: Processor - Pseudonymizer

   The :code:`pseudonymizer` works with two public keys for different roles.
   It is suggested to ensure that two different keys are being used such that the separation of the
   roles can be maintained.

   It is suggested to use the :code:`GCM` mode for encryption as it decouples the key length of the
   depseudo and analyst keys. This leads to additional 152 bytes of overhead for the encryption
   compared to the :code:`CTR` mode encrypter.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - pseudonymizername:
        type: pseudonymizer
        rules:
            - tests/testdata/rules/rules
        outputs:
            - kafka: pseudonyms_topic
        pubkey_analyst: /path/to/analyst_pubkey.pem
        pubkey_depseudo: /path/to/depseudo_pubkey.pem
        hash_salt: secret_salt
        regex_mapping: /path/to/regex_mapping.json
        max_cached_pseudonyms: 1000000
        mode: GCM

.. autoclass:: logprep.processor.pseudonymizer.processor.Pseudonymizer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.pseudonymizer.rule
"""

import re
from functools import cached_property, lru_cache
from itertools import chain
from typing import Pattern
from urllib.parse import parse_qs, urlencode, urlparse

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.factory_error import InvalidConfigurationError
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.pseudonymizer.rule import PseudonymizerRule
from logprep.util.getter import GetterFactory
from logprep.util.hasher import SHA256Hasher
from logprep.util.helper import add_fields_to, get_dotted_field_value
from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
    Encrypter,
)
from logprep.util.url.url import extract_urls


class Pseudonymizer(FieldManager):
    """Pseudonymize log events to conform to EU privacy laws."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
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
        repeatedly) and the load on subsequent components (i.e. Logstash or Opensearch).
        In case the cache size has been exceeded, the least recently used
        entry is deleted. Has to be greater than 0.
        """
        max_cached_pseudonymized_urls: int = field(
            validator=[validators.instance_of(int), validators.gt(0)], default=10000
        )
        """The maximum number of cached pseudonymized urls. Default is 10000.
        Behaves similarly to the max_cached_pseudonyms. Has to be greater than 0."""
        mode: str = field(
            validator=[validators.instance_of(str), validators.in_(("GCM", "CTR"))], default="GCM"
        )
        """Optional mode of operation for the encryption. Can be either 'GCM' or 'CTR'.
        Default is 'GCM'.
        """

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

        new_results: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of new pseudodonyms",
                name="pseudonymizer_new_results",
            )
        )
        """Number of new pseudodonyms"""
        cached_results: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of resolved from cache pseudonyms",
                name="pseudonymizer_cached_results",
            )
        )
        """Number of resolved from cache pseudonyms"""
        num_cache_entries: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of pseudonyms in cache",
                name="pseudonymizer_num_cache_entries",
            )
        )
        """Number of pseudonyms in cache"""
        cache_load: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Relative cache load.",
                name="pseudonymizer_cache_load",
            )
        )
        """Relative cache load."""

    HASH_PREFIX = "<pseudonym:"
    HASH_SUFFIX = ">"

    pseudonymized_pattern: Pattern = re.compile(rf"^{HASH_PREFIX}(.+?){HASH_SUFFIX}$")

    rule_class = PseudonymizerRule

    @cached_property
    def _hasher(self):
        return SHA256Hasher()

    @cached_property
    def _encrypter(self) -> Encrypter:
        if self._config.mode == "CTR":
            encrypter = DualPKCS1HybridCTREncrypter()
        else:
            encrypter = DualPKCS1HybridGCMEncrypter()
        encrypter.load_public_keys(self._config.pubkey_analyst, self._config.pubkey_depseudo)
        return encrypter

    @cached_property
    def _regex_mapping(self) -> dict:
        return GetterFactory.from_string(self._config.regex_mapping).get_yaml()

    @cached_property
    def _get_pseudonym_dict_cached(self):
        return lru_cache(maxsize=self._config.max_cached_pseudonyms)(self._pseudonymize)

    @cached_property
    def _pseudonymize_url_cached(self):
        return lru_cache(maxsize=self._config.max_cached_pseudonymized_urls)(self._pseudonymize_url)

    def setup(self):
        super().setup()
        self._replace_regex_keywords_by_regex_expression()

    def _replace_regex_keywords_by_regex_expression(self):
        for rule in self.rules:
            for dotted_field, regex_keyword in rule.pseudonyms.items():
                if regex_keyword in self._regex_mapping:
                    rule.pseudonyms[dotted_field] = re.compile(self._regex_mapping[regex_keyword])
                elif isinstance(regex_keyword, str):  # after the first run, the regex is compiled
                    raise InvalidConfigurationError(
                        f"Regex keyword '{regex_keyword}' not found in regex_mapping '{self._config.regex_mapping}'"
                    )

    def _apply_rules(self, event: dict, rule: PseudonymizerRule):
        source_dict = {}
        for source_field in rule.pseudonyms:
            source_dict[source_field] = get_dotted_field_value(event, source_field)
        self._handle_missing_fields(event, rule, source_dict.keys(), source_dict.values())

        for dotted_field, field_value in source_dict.items():
            regex = rule.pseudonyms[dotted_field]
            if field_value is None:
                continue
            if isinstance(field_value, list):
                field_value = [
                    self._pseudonymize_field(rule, dotted_field, regex, str(value))
                    for value in field_value
                ]
            else:
                field_value = self._pseudonymize_field(rule, dotted_field, regex, field_value)
            add_fields_to(
                event, fields={dotted_field: field_value}, rule=rule, overwrite_target=True
            )
        if "@timestamp" in event:
            for pseudonym, _ in self.result.data:
                pseudonym["@timestamp"] = event["@timestamp"]
        self._update_cache_metrics()

    def _pseudonymize_field(
        self, rule: PseudonymizerRule, dotted_field: str, regex: Pattern, field_value: str
    ) -> str:
        if regex.groups <= 1:
            plaintext_values = set(value for value in regex.findall(field_value) if value)
        else:
            plaintext_values = set(chain(*[value for value in regex.findall(field_value) if value]))
        if plaintext_values and dotted_field in rule.url_fields:
            for url_string in extract_urls(field_value):
                field_value = field_value.replace(
                    url_string, self._pseudonymize_url_cached(url_string)
                )
                if url_string in plaintext_values:
                    plaintext_values.remove(url_string)
        if plaintext_values:
            pseudonymized_values = [self._pseudonymize_string(value) for value in plaintext_values]
            pseudonymize = zip(plaintext_values, pseudonymized_values)
            for clear_value, pseudonymized_value in pseudonymize:
                if clear_value:
                    field_value = re.sub(re.escape(clear_value), pseudonymized_value, field_value)
        return field_value

    def _pseudonymize_string(self, value: str) -> str:
        if self.pseudonymized_pattern.match(value):
            return value
        pseudonym_dict = self._get_pseudonym_dict_cached(value)
        extra = (pseudonym_dict, self._config.outputs)
        if extra not in self.result.data:
            self.result.data.append(extra)
        return self._wrap_hash(pseudonym_dict["pseudonym"])

    def _pseudonymize(self, value):
        hash_string = self._hasher.hash_str(value, salt=self._config.hash_salt)
        encrypted_origin = self._encrypter.encrypt(value)
        return {"pseudonym": hash_string, "origin": encrypted_origin}

    def _pseudonymize_url(self, url_string: str) -> str:
        if url_string.startswith(("http://", "https://")):
            parsed_url = urlparse(url_string)
        else:
            parsed_url = urlparse(f"http://{url_string}")
        if parsed_url.hostname:
            splitted_hostname = parsed_url.hostname.split(".")
            if len(splitted_hostname) > 2:
                subdomain = ".".join(splitted_hostname[0:-2])
                url_string = url_string.replace(subdomain, self._pseudonymize_string(subdomain))
        if parsed_url.fragment:
            url_string = url_string.replace(
                f"#{parsed_url.fragment}", f"#{self._pseudonymize_string(parsed_url.fragment)}"
            )
        if parsed_url.username:
            auth_string = f"{parsed_url.username}:{parsed_url.password}"
            url_string = url_string.replace(auth_string, self._pseudonymize_string(auth_string))
        if parsed_url.path and len(parsed_url.path) > 1:
            url_string = url_string.replace(
                parsed_url.path[1:], self._pseudonymize_string(parsed_url.path[1:])
            )
        if parsed_url.query:
            query_parts = parse_qs(parsed_url.query)
            pseudonymized_query_parts = {
                key: [self._pseudonymize_string(value) for value in values if value]
                for key, values in query_parts.items()
            }
            pseudonymized_query = urlencode(
                pseudonymized_query_parts, safe="<pseudonym:>", doseq=True
            )
            url_string = url_string.replace(parsed_url.query, pseudonymized_query)
        self.metrics.pseudonymized_urls += 1
        return url_string

    def _wrap_hash(self, hash_string: str) -> str:
        return self.HASH_PREFIX + hash_string + self.HASH_SUFFIX

    def _update_cache_metrics(self):
        cache_info_pseudonyms = self._get_pseudonym_dict_cached.cache_info()
        cache_info_urls = self._pseudonymize_url_cached.cache_info()
        self.metrics.new_results += cache_info_pseudonyms.misses + cache_info_urls.misses
        self.metrics.cached_results += cache_info_pseudonyms.hits + cache_info_urls.hits
        self.metrics.num_cache_entries += cache_info_pseudonyms.currsize + cache_info_urls.currsize
        self.metrics.cache_load += (cache_info_pseudonyms.currsize + cache_info_urls.currsize) / (
            cache_info_pseudonyms.maxsize + cache_info_urls.maxsize
        )
