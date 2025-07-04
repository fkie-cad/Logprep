# pylint: disable=missing-docstring
# pylint: disable=protected-access
from pathlib import Path
from unittest import mock

from logprep.ng.event.log_event import LogEvent
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

    expected_metrics: list = []

    def test_domain_resolution_adds_resolved_ip(self):
        document = {"url": {"domain": "example.org"}}
        rule = {
            "filter": "url.domain",
            "domain_resolver": {"source_fields": ["url.domain"], "target_field": "url.resolved_ip"},
        }
        self._load_rule(rule)
        log_event = LogEvent(document, original=b"test_message")

        with mock.patch("socket.gethostbyname", return_value="93.184.216.34"):
            self.object.process(log_event)

        assert "resolved_ip" in log_event.data["url"]
