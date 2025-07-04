# pylint: disable=missing-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestIpInformer(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_ip_informer",
        "rules": ["tests/testdata/unit/ip_informer/rules"],
    }

    expected_metrics: list = []

    def test_ip_informer_instantiates(self):
        rule = {
            "filter": "client.ip",
            "ip_informer": {"source_fields": ["client.ip"], "target_field": "client.ip_info"},
        }
        self._load_rule(rule)
        document = {"client": {"ip": "192.168.1.1"}}
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        assert "client" in log_event.data
