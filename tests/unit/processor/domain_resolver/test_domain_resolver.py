# pylint: disable=missing-docstring
import re
import socket
from os.path import exists
from pathlib import Path
from time import sleep

import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.domain_resolver.factory import DomainResolverFactory
from tests.unit.processor.base import BaseProcessorTestCase

rel_tld_list_path = "tests/testdata/external/public_suffix_list.dat"
tld_list = f"file://{Path().absolute().joinpath(rel_tld_list_path).as_posix()}"


class TestDomainResolver(BaseProcessorTestCase):

    CONFIG = {
        "type": "domain_resolver",
        "generic_rules": ["tests/testdata/unit/domain_resolver/rules/generic"],
        "specific_rules": ["tests/testdata/unit/domain_resolver/rules/specific"],
        "tld_list": tld_list,
        "timeout": 0.25,
        "max_cached_domains": 1000000,
        "max_caching_days": 1,
        "hash_salt": "a_secret_tasty_ingredient",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    def test_domain_to_ip_resolved_and_added(self, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"url": "google.de"}

        self.object.process(document)

        assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved_ip", ""))

    @pytest.mark.skipif(not exists(tld_list.split("file://")[-1]), reason="Tld-list required.")
    def test_invalid_dots_domain_to_ip_produces_warning(self):
        assert self.object.ps.processed_count == 0
        document = {"url": "google..invalid.de"}

        with pytest.raises(
            ProcessingWarning,
            match=r"DomainResolver \(test-domain-resolver\)\: encoding with \'idna\' codec failed "
            r"\(UnicodeError\: label empty or too long\) for domain \'google..invalid.de\'",
        ):
            self.object.process(document)

    def test_url_to_ip_resolved_and_added(self, monkeypatch):
        def mockreturn(domain):
            if domain == "www.google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"url": "https://www.google.de/something"}

        self.object.process(document)

        assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved_ip", ""))

    def test_domain_to_ip_not_resolved(self, monkeypatch):
        def mockreturn(_):
            return "1.2.3.4"

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"url": "google.thisisnotavalidtld"}

        self.object.process(document)

        assert document.get("resolved_ip") is None

    def test_domain_to_ip_timed_out(self, monkeypatch):
        def mockreturn(_):
            sleep(0.3)  # nosemgrep
            return "1.2.3.4"

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"url": "google.de"}

        self.object.process(document)

        assert document.get("resolved_ip") is None

    def test_configured_dotted_subfield(self, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"source": "google.de"}

        self.object.process(document)
        assert re.match(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved", "").get("ip")
        )

    def test_duplication_error(self, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert self.object.ps.processed_count == 0
        document = {"client": "google.de"}

        # Due to duplication error logprep raises an ProcessingWarning
        with pytest.raises(
            ProcessingWarning,
            match=r"DomainResolver \(.+\): The "
            r"following fields already existed and were not overwritten by the "
            r"DomainResolver: resolved_ip",
        ):
            self.object.process(document)
