# pylint: disable=missing-docstring
# pylint: disable=protected-access
import datetime
import re
import time
from copy import deepcopy
from typing import cast
from unittest import mock
from unittest.mock import MagicMock

import pytest
from dns.resolver import LifetimeTimeout, NoNameservers, NoAnswer

from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.ng.processor.domain_resolver.processor import (
    DomainResolver,
    FailureType,
    FailedResult,
    SuccessResult,
)

from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase


class TestDomainResolver(BaseProcessorTestCase):
    CONFIG = {
        "type": "domain_resolver",
        "rules": ["tests/testdata/unit/domain_resolver/rules"],
        "timeout": 0.25,
        "max_cached_domains": 1000000,
        "max_caching_days": 1,
        "hash_salt": "a_secret_tasty_ingredient",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    expected_metrics = [
        "logprep_domain_resolver_total_urls",
        "logprep_domain_resolver_resolved_new",
        "logprep_domain_resolver_resolved_cached",
        "logprep_domain_resolver_resolved_domains",
        "logprep_domain_resolver_timeouts",
        "logprep_domain_resolver_invalid_domains",
        "logprep_domain_resolver_unknown_domains",
        "logprep_domain_resolver_timeouts_cached",
    ]

    def test_domain_to_ip_resolved_and_added(self):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        fqdn = "google.de"
        self._load_rule(rule)
        document = {"fqdn": fqdn}
        expected = {"fqdn": fqdn, "resolved_ip": "1.2.3.4"}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
            mock_resolve.assert_called_once()
            mock_resolve.assert_called_with(fqdn, "A")
        assert document == expected

    def test_domain_to_ip_timeout_cached(self):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"fqdn": "google.de"}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            assert len(self.object._timeout_cache) == 0
            self.object.process(document)
            mock_resolve.assert_called_once()
            mock_resolve.side_effect = None
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            assert len(self.object._timeout_cache) == 1
            self.object.process(document)
            assert len(self.object._timeout_cache) == 1
            mock_resolve.assert_called_once()
        assert document.get("reoslved_ip") is None

    def test_url_to_ip_resolved_and_added(self):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document == expected

    @pytest.mark.skip_autouse
    def test_domain_invalid(self):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"fqdn": "https://www.google.de"}

        assert self.object.config.cache_enabled is True

        with mock.patch.object(self.object, "_resolve_with_cache") as mock_resolve:
            self.object.process(document)
            mock_resolve.assert_called_with("www.google.de")

        document = {"fqdn": "http://"}
        with mock.patch.object(self.object, "_resolve_with_cache") as mock_resolve:
            self.object.process(document)
            mock_resolve.assert_not_called()

    def test_domain_ip_map_not_in_cache_gets_pruned(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10, "cache_prune_interval": 0.1})
        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            domain_resolver.process(document)
        document = {"url": "https://www.not-google.de"}
        expected = {"url": "https://www.not-google.de", "resolved_ip": "5.6.7.8"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("5.6.7.8", mock_resolve)
            domain_resolver.process(document)
        assert document == expected
        assert len(domain_resolver._domain_ip_map) == len(domain_resolver._domain_cache)
        domain_resolver._domain_cache.popitem()
        assert len(domain_resolver._domain_ip_map) > len(domain_resolver._domain_cache)
        domain_resolver._domain_ip_map_prune_timer.reset()
        domain_resolver._prune_domain_ip_map()
        assert len(domain_resolver._domain_ip_map) > len(domain_resolver._domain_cache)
        time.sleep(0.1)
        domain_resolver._prune_domain_ip_map()
        assert len(domain_resolver._domain_ip_map) == len(domain_resolver._domain_cache)

    def test_timeout_cache_gets_pruned(self):
        def mark_cache_item_as_decayed_and_return_hash(resolver):
            cached_hash_to_decay = next(iter(resolver._timeout_cache))
            resolver._timeout_cache[cached_hash_to_decay] = datetime.datetime.min
            return cached_hash_to_decay

        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10})
        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            domain_resolver.process(document)
        document = {"url": "https://www.not-google.de"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("5.6.7.8", mock_resolve)
            domain_resolver.process(document)
        assert document.get("resolved_ip") is None
        assert len(domain_resolver._timeout_cache) == 2

        domain_resolver._timeout_cache.prune_decayed()
        assert len(domain_resolver._timeout_cache) == 2

        cached_hash = mark_cache_item_as_decayed_and_return_hash(domain_resolver)
        domain_resolver._timeout_cache.prune_decayed()
        assert len(domain_resolver._timeout_cache) == 2

        domain_resolver._timeout_cache._prune_timer._finished_sec = 0
        domain_resolver._timeout_cache.prune_decayed()
        assert len(domain_resolver._timeout_cache) == 1
        assert cached_hash not in domain_resolver._timeout_cache

        cached_hash = mark_cache_item_as_decayed_and_return_hash(domain_resolver)
        domain_resolver._timeout_cache._prune_timer._finished_sec = 0
        domain_resolver._timeout_cache.prune_decayed()
        assert len(domain_resolver._timeout_cache) == 0
        assert cached_hash not in domain_resolver._timeout_cache

    def test_domain_timeout_gets_not_resolved(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }

        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        self._load_rule(rule)
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_timeout_check("domain")
            assert isinstance(result, SuccessResult)
            assert result.resolved_ip == "1.2.3.4"
            assert len(domain_resolver._timeout_cache) == 0

        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        self._load_rule(rule)
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_timeout_check("domain")
            assert isinstance(result, FailedResult)
            assert result.failure_type == FailureType.TIMEOUT
            assert len(domain_resolver._timeout_cache) == 1

        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_timeout_check("domain")
            assert isinstance(result, FailedResult)
            assert result.failure_type == FailureType.TIMEOUT
            assert len(domain_resolver._timeout_cache) == 1

            domain_resolver._timeout_cache.clear()

            result = domain_resolver._resolve_with_timeout_check("domain")
            assert isinstance(result, SuccessResult)
            assert result.resolved_ip == "1.2.3.4"
            assert len(domain_resolver._timeout_cache) == 0

    def test_do_nothing_if_source_not_in_event(self):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["not_available"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something"}
        self.object.process(document)
        assert document == expected

    def test_url_to_ip_resolved_and_added_with_cache_disabled(self):
        config = deepcopy(self.CONFIG)
        config.update({"cache_enabled": False})
        domain_resolver = Factory.create({"resolver": config})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            domain_resolver.process(document)
        assert document == expected

    def test_domain_to_ip_not_resolved(self):
        domain = "google.thisisnotavalidtld"
        document = {"url": domain}
        self.object.process(document)
        assert document.get("resolved_ip") is None

    def test_domain_to_ip_timed_out(self):
        document = {"url": "google.de"}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document.get("resolved_ip") is None

    def test_configured_dotted_subfield(self):
        document = {"source": "google.de"}
        expected = {"source": "google.de", "resolved": {"ip": "1.2.3.4"}}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document == expected

    @staticmethod
    def _mock_resolve_answer(expected_ip, mock_resolve):
        mock_answer = MagicMock()
        mock_answer.address = expected_ip
        mock_resolve.return_value = [mock_answer]

    def test_duplication_error(self):
        document = {"client": "google.de"}

        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = self.object.process(document)
            assert len(result.warnings) == 1
            assert isinstance(result.warnings[0], FieldExistsWarning)

    def test_no_duplication_error(self):
        document = {"client_2": "google.de"}
        expected = {"client_2": "google.de", "resolved_ip": "1.2.3.4"}

        # Rules have same effect, but are equal and thus one is ignored
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document == expected

    def test_overwrite_target_field(self):
        document = {"client": "google.de", "resolved": "this will be overwritten"}
        expected = {"client": "google.de", "resolved": "1.2.3.4"}
        rule_dict = {
            "filter": "client",
            "domain_resolver": {
                "source_fields": ["client"],
                "target_field": "resolved",
                "overwrite_target": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document == expected

    def test_delete_source_field(self):
        document = {"client": "google.de", "resolved": "this will be overwritten"}
        expected = {"resolved": "1.2.3.4"}
        rule_dict = {
            "filter": "client",
            "domain_resolver": {
                "source_fields": ["client"],
                "target_field": "resolved",
                "overwrite_target": True,
                "delete_source_fields": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            self.object.process(document)
        assert document == expected

    def test_resolve_domain_syntax_error(self):
        domain = ".."
        result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.INVALID

    def test_resolve_domain_too_big(self):
        domain = "0" * 64
        result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.INVALID

    def test_resolve_domain_no_answer(self):
        domain = "https://google.de"
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = NoAnswer
            result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.NO_ANSWER

    def test_resole_domain_no_nameservers(self):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"fqdn": "https://www.google.de"}
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = NoNameservers
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = self.object.process(document)
            assert len(result.warnings) == 1
            assert isinstance(result.warnings[0], ProcessingWarning)
            assert re.match(
                ".*All nameservers failed to answer the query*", str(result.warnings[0])
            )
