# pylint: disable=missing-docstring
# pylint: disable=protected-access
from copy import deepcopy
from multiprocessing import context
from pathlib import Path
from unittest import mock

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.domain_resolver.processor import ResolveStatus
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase

REL_TLD_LIST_PATH = "tests/testdata/external/public_suffix_list.dat"
TLD_LIST = f"file://{Path().absolute().joinpath(REL_TLD_LIST_PATH).as_posix()}"


class TestDomainResolver(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_domain_resolver",
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
        "logprep_domain_resolver_timeouts",
        "logprep_domain_resolver_invalid_domains",
        "logprep_domain_resolver_unknown_domains",
    ]

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_domain_to_ip_resolved_and_added(self, mock_gethostbyname):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"fqdn": "google.de"}
        expected = {"fqdn": "google.de", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        mock_gethostbyname.assert_called_once()
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_domain_to_ip_resolved_and_added_from_cache(self, mock_gethostbyname):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"fqdn": "google.de"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        document = {"fqdn": "google.de"}
        expected = {"fqdn": "google.de", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        mock_gethostbyname.assert_called_once()
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added(self, _):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_domain_ip_map_greater_cache(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 1})
        self.object = Factory.create({"resolver": config})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        log_event = LogEvent(document, original=b"")
        with mock.patch("socket.gethostbyname", return_value="1.2.3.4"):
            self.object.process(log_event)
        document = {"url": "https://www.google.de/something_else"}
        expected = {"url": "https://www.google.de/something_else", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")
        with mock.patch("socket.gethostbyname", return_value="1.2.3.4"):
            self.object.process(log_event)
        assert log_event.data == expected

    def test_do_nothing_if_source_not_in_event(self):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["not_available"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added_with_debug_cache(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"debug_cache": True})
        self.object = Factory.create({"resolver": config})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {
            "url": "https://www.google.de/something",
            "resolved_ip_debug": {"obtained_from_cache": False, "cache_size": 1},
            "resolved_ip": "1.2.3.4",
        }
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_from_cache_and_added_with_debug_cache(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"debug_cache": True})
        self.object = Factory.create({"resolver": config})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        document = {"url": "https://www.google.de/something_else"}
        expected = {
            "url": "https://www.google.de/something_else",
            "resolved_ip_debug": {"obtained_from_cache": True, "cache_size": 1},
            "resolved_ip": "1.2.3.4",
        }
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added_with_cache_disabled(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"cache_enabled": False})
        self.object = Factory.create({"resolver": config})
        rule = {
            "filter": "url",
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", side_effect=UnicodeError("invalid"), return_value="1.2.3.4")
    def test_invalid_domain_with_unicode_error_is_resolved_to_none_and_returns_status(self, _):
        resolved_ip, status = self.object._resolve_ip("google..invalid.de")
        assert resolved_ip is None
        assert status is ResolveStatus.INVALID

    @mock.patch("socket.gethostbyname", side_effect=context.TimeoutError, return_value="1.2.3.4")
    def test_valid_domain_with_timeout_error_is_resolved_to_none_and_returns_status(self, _):
        resolved_ip, status = self.object._resolve_ip("google.de")
        assert resolved_ip is None
        assert status is ResolveStatus.TIMEOUT

    @mock.patch("socket.gethostbyname", side_effect=OSError, return_value="1.2.3.4")
    def test_unknown_domain_with_os_error_is_resolved_to_none_and_returns_status(self, _):
        resolved_ip, status = self.object._resolve_ip("google.de")
        assert resolved_ip is None
        assert status is ResolveStatus.UNKNOWN

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_existing_domain_is_resolved_to_and_returns_status(self, _):
        resolved_ip, status = self.object._resolve_ip("google.de")
        assert resolved_ip == "1.2.3.4"
        assert status is ResolveStatus.SUCCESS

    def test_empty_domain_is_snot_resolved(self):
        document = {"url": " "}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data.get("resolved_ip") is None

    def test_domain_to_ip_not_resolved(self):
        document = {"url": "google.thisisnotavalidtld"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data.get("resolved_ip") is None

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4", side_effect=TimeoutError)
    def test_domain_to_ip_timed_out(self, _):
        document = {"url": "google.de"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data.get("resolved_ip") is None

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_configured_dotted_subfield(self, _):
        document = {"source": "google.de"}
        expected = {"source": "google.de", "resolved": {"ip": "1.2.3.4"}}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_field_exits_warning(self, _):
        document = {"client": "google.de"}
        log_event = LogEvent(document, original=b"")

        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_no_duplication_error(self, _):
        document = {"client_2": "google.de"}
        expected = {"client_2": "google.de", "resolved_ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"")

        # Rules have same effect, but are equal and thus one is ignored
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_overwrite_target_field(self, _):
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
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_delete_source_field(self, _):
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
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected
