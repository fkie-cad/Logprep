from os.path import exists
from pathlib import Path
import re
import socket
from time import sleep
from logging import getLogger

import pytest

pytest.importorskip("logprep.processor.domain_resolver")

from logprep.processor.domain_resolver.factory import DomainResolverFactory
from logprep.processor.base.processor import ProcessingWarning

logger = getLogger()
rel_tld_list_path = "tests/testdata/external/public_suffix_list.dat"
tld_list = f"file://{Path().absolute().joinpath(rel_tld_list_path).as_posix()}"
rules_dir = "tests/testdata/unit/domain_resolver/rules"


@pytest.fixture()
def domain_resolver():
    config = {
        "type": "domain_resolver",
        "rules": [rules_dir],
        "tld_list": tld_list,
        "timeout": 0.25,
        "max_cached_domains": 1000000,
        "max_caching_days": 1,
        "hash_salt": "a_secret_tasty_ingredient",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    domain_resolver = DomainResolverFactory.create("test-domain-resolver", config, logger)
    return domain_resolver


class TestDomainResolver:
    def test_domain_to_ip_resolved_and_added(self, domain_resolver, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"url": "google.de"}

        domain_resolver.process(document)

        assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved_ip", ""))

    @pytest.mark.skipif(not exists(tld_list.split("file://")[-1]), reason="Tld-list required.")
    def test_invalid_dots_domain_to_ip_produces_warning(self, domain_resolver):
        assert domain_resolver.ps.processed_count == 0
        document = {"url": "google..invalid.de"}

        with pytest.raises(
            ProcessingWarning,
            match=r"DomainResolver \(test-domain-resolver\)\: encoding with \'idna\' codec failed "
            r"\(UnicodeError\: label empty or too long\) for domain \'google..invalid.de\'",
        ):
            domain_resolver.process(document)

    def test_url_to_ip_resolved_and_added(self, domain_resolver, monkeypatch):
        def mockreturn(domain):
            if domain == "www.google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"url": "https://www.google.de/something"}

        domain_resolver.process(document)

        assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved_ip", ""))

    def test_domain_to_ip_not_resolved(self, domain_resolver, monkeypatch):
        def mockreturn(_):
            return "1.2.3.4"

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"url": "google.thisisnotavalidtld"}

        domain_resolver.process(document)

        assert document.get("resolved_ip") is None

    def test_domain_to_ip_timed_out(self, domain_resolver, monkeypatch):
        def mockreturn(_):
            sleep(0.3)
            return "1.2.3.4"

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"url": "google.de"}

        domain_resolver.process(document)

        assert document.get("resolved_ip") is None

    def test_configured_dotted_subfield(self, domain_resolver, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"source": "google.de"}

        domain_resolver.process(document)
        assert re.match(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", document.get("resolved", "").get("ip")
        )

    def test_duplication_error(self, domain_resolver, monkeypatch):
        def mockreturn(domain):
            if domain == "google.de":
                return "1.2.3.4"
            else:
                return None

        monkeypatch.setattr(socket, "gethostbyname", mockreturn)

        assert domain_resolver.ps.processed_count == 0
        document = {"client": "google.de"}

        # Due to duplication error logprep raises an ProcessingWarning
        with pytest.raises(
            ProcessingWarning,
            match=r"DomainResolver \(test-domain-resolver\): The "
            r"following fields already existed and were not overwritten by the "
            r"DomainResolver: resolved_ip",
        ) as e_info:
            domain_resolver.process(document)
