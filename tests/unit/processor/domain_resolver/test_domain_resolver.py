# pylint: disable=missing-docstring
# pylint: disable=protected-access
import hashlib
import logging
import os
import re
import shutil
import tempfile
from copy import deepcopy
from os.path import exists
from pathlib import Path
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.processor.base.exceptions import ProcessingWarning
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

    expected_metrics = [
        "logprep_domain_resolver_total_urls",
        "logprep_domain_resolver_resolved_new",
        "logprep_domain_resolver_resolved_cached",
        "logprep_domain_resolver_timeouts",
    ]

    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_domain_to_ip_resolved_and_added(self, mock_gethostbyname):
        rule = {
            "filter": "fqdn",
            "domain_resolver": {"source_fields": ["fqdn"]},
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
            "domain_resolver": {"source_fields": ["fqdn"]},
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
            "domain_resolver": {"source_fields": ["url"]},
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
            "domain_resolver": {"source_fields": ["url"]},
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
            "domain_resolver": {"source_fields": ["not_available"]},
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
            "domain_resolver": {"source_fields": ["url"]},
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
            "domain_resolver": {"source_fields": ["url"]},
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
            "domain_resolver": {"source_fields": ["url"]},
            "description": "",
        }
        self._load_specific_rule(rule)
        document = {"url": "https://www.google.de/something"}
        expected = {"url": "https://www.google.de/something", "resolved_ip": "1.2.3.4"}
        self.object.process(document)
        assert document == expected

    @responses.activate
    @mock.patch("socket.gethostbyname", return_value="1.2.3.4")
    def test_resolves_with_tld_extract_tld_lists(self, _):
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
        responses.add(responses.GET, "http://does_not_matter", response_content)
        config = deepcopy(self.CONFIG)
        config.update({"tld_lists": ["http://does_not_matter"]})
        domain_resolver = Factory.create({"test instance": config}, self.logger)
        document = {"url": "http://www.google.ac.at/some/text"}
        expected = {"url": "http://www.google.ac.at/some/text", "resolved_ip": "1.2.3.4"}
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
    def test_duplication_error(self, _, caplog):
        document = {"client": "google.de"}

        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*", caplog.text)

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

    @responses.activate
    def test_setup_downloads_tld_lists_to_separate_process_file(self):
        tld_list = "http://db-path-target/list.dat"
        tld_list_path = Path("/usr/bin/ls") if Path("/usr/bin/ls").exists() else Path("/bin/ls")
        tld_list_content = tld_list_path.read_bytes()
        expected_checksum = hashlib.md5(tld_list_content).hexdigest()  # nosemgrep
        responses.add(responses.GET, tld_list, tld_list_content)
        self.object._config.tld_lists = [tld_list]
        self.object.setup()
        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        downloaded_file = logprep_tmp_dir / f"{self.object.name}-tldlist-0.dat"
        assert downloaded_file.exists()
        downloaded_checksum = hashlib.md5(downloaded_file.read_bytes()).hexdigest()  # nosemgrep
        assert expected_checksum == downloaded_checksum
        # delete testfile
        shutil.rmtree(logprep_tmp_dir)

    @responses.activate
    def test_setup_doesnt_overwrite_already_existing_tld_list_file(self):
        tld_list = "http://db-path-target/list.dat"
        tld_list_content = "some content"
        responses.add(responses.GET, tld_list, tld_list_content.encode("utf8"))

        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        os.makedirs(logprep_tmp_dir, exist_ok=True)
        tld_temp_file = logprep_tmp_dir / f"{self.object.name}-tldlist-0.dat"

        pre_existing_content = "file exists already"
        tld_temp_file.touch()
        tld_temp_file.write_bytes(pre_existing_content.encode("utf8"))
        self.object._config.tld_lists = [tld_list]
        self.object.setup()
        assert tld_temp_file.exists()
        assert tld_temp_file.read_bytes().decode("utf8") == pre_existing_content
        assert tld_temp_file.read_bytes().decode("utf8") != tld_list_content
        shutil.rmtree(logprep_tmp_dir)  # delete testfile
