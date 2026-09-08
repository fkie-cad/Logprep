# pylint: disable=missing-docstring
# pylint: disable=protected-access
import re
import time
from copy import deepcopy
from typing import cast
from unittest import mock
from unittest.mock import MagicMock

from dns.resolver import LifetimeTimeout, NoNameservers, NoAnswer

from logprep.ng.abc.event import LogEvent, InputMeta
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.ng.processor.domain_resolver.processor import (
    DomainResolver,
    FailureType,
    FailedResult,
    SuccessResult,
)

from logprep.factory import Factory
from tests.unit.ng.processor.base import BaseProcessorTestCase


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

    async def test_domain_to_ip_resolved_and_added(self):
        await self.object.setup()
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        fqdn = "google.de"
        await self._load_rule(rule)
        document = {"fqdn": fqdn}
        expected = {"fqdn": fqdn, "resolved_ip": "1.2.3.4"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
            mock_resolve.assert_called_once()
            mock_resolve.assert_called_with(fqdn, "A")
        assert document == expected

    async def test_domain_to_ip_timeout_cached(self):
        await self.object.setup()
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"fqdn": "google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            assert len(self.object._timeout_cache) == 0
            await self.object.process(event)
            mock_resolve.assert_called_once()
            mock_resolve.side_effect = None
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            assert len(self.object._timeout_cache) == 1
            await self.object.process(event)
            assert len(self.object._timeout_cache) == 1
            mock_resolve.assert_called_once()
        assert event.data.get("reoslved_ip") is None

    async def test_url_to_ip_resolved_and_added(self):
        await self.object.setup()
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document == expected

    async def test_domain_invalid(self):
        await self.object.setup()
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"fqdn": "https://www.google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())

        assert self.object.config.cache_enabled is True

        with mock.patch.object(self.object, "_resolve_with_cache") as mock_resolve:
            await self.object.process(event)
            mock_resolve.assert_called_with("www.google.de")

        document = {"fqdn": "http://"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object, "_resolve_with_cache") as mock_resolve:
            await self.object.process(event)
            mock_resolve.assert_not_called()

    async def test_domain_ip_map_not_in_cache_gets_pruned(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10, "cache_prune_interval": 0.1})
        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        await domain_resolver.setup()
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"url": "https://www.google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await domain_resolver.process(event)
        document = {"url": "https://www.not-google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"url": "https://www.not-google.de", "resolved_ip": "5.6.7.8"}
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("5.6.7.8", mock_resolve)
            await domain_resolver.process(event)
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

    async def test_timeout_cache_gets_pruned(self):
        def mark_cache_item_as_decayed_and_return_hash(resolver):
            cached_hash_to_decay = next(iter(resolver._timeout_cache))
            resolver._timeout_cache[cached_hash_to_decay] = 0
            return cached_hash_to_decay

        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10})
        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        await domain_resolver.setup()
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"url": "https://www.google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await domain_resolver.process(event)
        document = {"url": "https://www.not-google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("5.6.7.8", mock_resolve)
            await domain_resolver.process(event)
        assert event.data.get("resolved_ip") is None
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

    async def test_domain_timeout_gets_not_resolved(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 10})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }

        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        await domain_resolver.setup()
        await self._load_rule(rule)
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_cache("domain")
            assert isinstance(result, SuccessResult)
            assert result.resolved_ip == "1.2.3.4"
            assert len(domain_resolver._timeout_cache) == 0

        domain_resolver: DomainResolver = cast(DomainResolver, Factory.create({"resolver": config}))
        await domain_resolver.setup()
        await self._load_rule(rule)
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_cache("domain")
            assert isinstance(result, FailedResult)
            assert result.failure_type == FailureType.TIMEOUT
            assert len(domain_resolver._timeout_cache) == 1

        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = domain_resolver._resolve_with_cache("domain")
            assert isinstance(result, FailedResult)
            assert result.failure_type == FailureType.TIMEOUT
            assert len(domain_resolver._timeout_cache) == 1

            domain_resolver._timeout_cache.clear()

            result = domain_resolver._resolve_with_cache("domain")
            assert isinstance(result, SuccessResult)
            assert result.resolved_ip == "1.2.3.4"
            assert len(domain_resolver._timeout_cache) == 0

    async def test_do_nothing_if_source_not_in_event(self):
        await self.object.setup()
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["not_available"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        assert document == expected

    async def test_url_to_ip_resolved_and_added_with_cache_disabled(self):
        config = deepcopy(self.CONFIG)
        config.update({"cache_enabled": False})
        domain_resolver = cast(DomainResolver, Factory.create({"resolver": config}))
        await domain_resolver.setup()
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(domain_resolver._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await domain_resolver.process(event)
        assert document == expected

    async def test_domain_to_ip_not_resolved(self):
        domain = "google.thisisnotavalidtld"
        document = {"url": domain}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        assert document.get("resolved_ip") is None

    async def test_domain_to_ip_timed_out(self):
        await self.object.setup()
        document = {"url": "google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = LifetimeTimeout
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document.get("resolved_ip") is None

    async def test_configured_dotted_subfield(self):
        await self.object.setup()
        document = {"source": "google.de"}
        expected = {"source": "google.de", "resolved": {"ip": "1.2.3.4"}}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document == expected

    @staticmethod
    def _mock_resolve_answer(expected_ip, mock_resolve):
        mock_answer = MagicMock()
        mock_answer.address = expected_ip
        mock_resolve.return_value = [mock_answer]

    async def test_duplication_error(self):
        await self.object.setup()
        document = {"client": "google.de"}

        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = await self.object.process(event)
            assert len(result.warnings) == 1
            assert isinstance(result.warnings[0], FieldExistsWarning)

    async def test_no_duplication_error(self):
        await self.object.setup()
        document = {"client_2": "google.de"}
        expected = {"client_2": "google.de", "resolved_ip": "1.2.3.4"}

        event = LogEvent(document, original=b"", input_meta=InputMeta())
        # Rules have same effect, but are equal and thus one is ignored
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document == expected

    async def test_overwrite_target_field(self):
        await self.object.setup()
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
        await self._load_rule(rule_dict)
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document == expected

    async def test_delete_source_field(self):
        await self.object.setup()
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
        await self._load_rule(rule_dict)
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            await self.object.process(event)
        assert document == expected

    async def test_resolve_domain_syntax_error(self):
        await self.object.setup()
        domain = ".."
        result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.INVALID

    async def test_resolve_domain_too_big(self):
        await self.object.setup()
        domain = "0" * 64
        result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.INVALID

    async def test_resolve_domain_no_answer(self):
        await self.object.setup()
        domain = "https://google.de"
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = NoAnswer
            result = self.object._resolve_ip(domain)
        assert result.failure_type == FailureType.NO_ANSWER

    async def test_resole_domain_no_nameservers(self):
        await self.object.setup()
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        await self._load_rule(rule)
        document = {"fqdn": "https://www.google.de"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        with mock.patch.object(self.object._dns_resolver, "resolve") as mock_resolve:
            mock_resolve.side_effect = NoNameservers
            self._mock_resolve_answer("1.2.3.4", mock_resolve)
            result = await self.object.process(event)
            assert len(result.warnings) == 1
            assert isinstance(result.warnings[0], ProcessingWarning)
            assert re.match(
                ".*All nameservers failed to answer the query*", str(result.warnings[0])
            )
