# pylint: disable=missing-docstring
# pylint: disable=protected-access
from copy import deepcopy
from os.path import exists
from pathlib import Path
from unittest import mock

import pytest
from requests import Response

from logprep.processor.base.exceptions import DuplicationError, ProcessingWarning
from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase

REL_TLD_LIST_PATH = "tests/testdata/external/public_suffix_list.dat"
TLD_LIST = f"file://{Path().absolute().joinpath(REL_TLD_LIST_PATH).as_posix()}"


class TestDomainResolver(BaseProcessorTestCase):

    CONFIG = {
        "type": "domain_resolver",
        "generic_rules": ["tests/testdata/unit/domain_resolver/rules/generic"],
        "specific_rules": ["tests/testdata/unit/domain_resolver/rules/specific"],
        "timeout": 0.25,
        "max_cached_domains": 1000000,
        "max_caching_days": 1,
        "hash_salt": "a_secret_tasty_ingredient",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_domain_to_ip_resolved_and_added(self, mock_gethostbyname):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_url_or_domain": "fqdn"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"fqdn": "google.de"}
        expected = {"fqdn": "google.de", "resolved_ip": "1.2.3.4"}
        self.object.process(document)
        mock_gethostbyname.assert_called_once()
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_domain_to_ip_resolved_and_added_from_cache(self, mock_gethostbyname):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_url_or_domain": "fqdn"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"fqdn": "google.de"}
        self.object.process(document)
        document = {"fqdn": "google.de"}
        expected = {"fqdn": "google.de", "resolved_ip": "1.2.3.4"}
        self.object.process(document)
        mock_gethostbyname.assert_called_once()
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added(self, _):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "url"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        self.object.process(document)
        assert document == expected

    def test_domain_ip_map_greater_cache(self):
        config = deepcopy(self.CONFIG)
        config.update({"max_cached_domains": 1})
        self.object = Factory.create({"resolver": config}, self.logger)
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "url"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        with mock.patch("socket.gethostbyname", return_value="1.2.3.4"):
            self.object.process(document)
        document = {"url": "https://www.google.de/something_else"}
        expected = {"url": "https://www.google.de/something_else", "resolved_ip": "1.2.3.4"}
        with mock.patch("socket.gethostbyname", return_value="1.2.3.4"):
            self.object.process(document)
        assert document == expected

    def test_do_nothing_if_source_not_in_event(self):
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "not_available"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something"}
        self.object.process(document)
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added_with_debug_cache(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"debug_cache": True})
        self.object = Factory.create({"resolver": config}, self.logger)
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "url"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {
            "url": "https://www.google.de/something",
            "resolved_ip_debug": {"obtained_from_cache": False, "cache_size": 1},
            "resolved_ip": "1.2.3.4",
        }
        self.object.process(document)
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_from_cache_and_added_with_debug_cache(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"debug_cache": True})
        self.object = Factory.create({"resolver": config}, self.logger)
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "url"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        self.object.process(document)
        document = {"url": "https://www.google.de/something_else"}
        expected = {
            "url": "https://www.google.de/something_else",
            "resolved_ip_debug": {"obtained_from_cache": True, "cache_size": 1},
            "resolved_ip": "1.2.3.4",
        }
        self.object.process(document)
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_url_to_ip_resolved_and_added_with_cache_disabled(self, _):
        config = deepcopy(self.CONFIG)
        config.update({"cache_enabled": False})
        self.object = Factory.create({"resolver": config}, self.logger)
        rule = {
            "filter": "url",
            "domain_resolver": {"source_url_or_domain": "url"},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        self.object.process(document)
        assert document == expected

    @mock.patch("requests.sessions.Session.get")
    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isfile", return_value=True)
    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_resolves_with_tld_extract_tld_lists(self, _, __, ___, mock_get):
        response_content = """
// at : https://en.wikipedia.org/wiki/.at
// Confirmed by registry <it@nic.at> 2008-06-17
at
ac.at
co.at
gv.at
or.at
sth.ac.at
        """
        response = Response()
        type(response).text = mock.PropertyMock(return_value=response_content)
        type(response).status_code = mock.PropertyMock(return_value=200)
        mock_get.return_value = response
        config = deepcopy(self.CONFIG)
        config.update({"tld_lists": ["file://does_not_matter"]})
        domain_resolver = Factory.create({"test instance": config}, self.logger)
        document = {"url": "www.google.ac.at"}
        expected = {"url": "www.google.ac.at", "resolved_ip": "1.2.3.4"}
        domain_resolver.process(document)
        assert document == expected

    @pytest.mark.skipif(not exists(TLD_LIST.split("file://")[-1]), reason="Tld-list required.")
    def test_invalid_dots_domain_to_ip_produces_warning(self):
        config = deepcopy(self.CONFIG)
        config.update({"tld_list": TLD_LIST})
        domain_resolver = Factory.create({"test instance": config}, self.logger)

        assert self.object.metrics.number_of_processed_events == 0
        document = {"url": "google..invalid.de"}

        with pytest.raises(
            ProcessingWarning,
            match=r"DomainResolver \(test-domain-resolver\)\: encoding with \'idna\' codec failed "
            r"\(UnicodeError\: label empty or too long\) for domain \'google..invalid.de\'",
        ):
            domain_resolver.process(document)

    def test_domain_to_ip_not_resolved(self):
        document = {"url": "google.thisisnotavalidtld"}
        self.object.process(document)
        assert document.get("resolved_ip") is None

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4", side_effect=TimeoutError)
    def test_domain_to_ip_timed_out(self, _):
        document = {"url": "google.de"}
        self.object.process(document)
        assert document.get("resolved_ip") is None

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_configured_dotted_subfield(self, _):
        document = {"source": "google.de"}
        expected = {"source": "google.de", "resolved": {"ip": "1.2.3.4"}}
        self.object.process(document)
        assert document == expected

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_duplication_error(self, _):
        document = {"client": "google.de"}

        # Due to duplication error logprep raises an ProcessingWarning
        with pytest.raises(
            DuplicationError,
            match=r"\('Test Instance Name', 'The following fields could not be written, "
            r"because one or more subfields existed and could not be extended: resolved_ip'\)",
        ):
            self.object.process(document)

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_no_duplication_error(self, _):
        document = {"client_2": "google.de"}
        expected = {"client_2": "google.de", "resolved_ip": "1.2.3.4"}

        # Rules have same effect, but are equal and thus one is ignored
        self.object.process(document)
        assert document == expected

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
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert document == expected

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
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert document == expected
