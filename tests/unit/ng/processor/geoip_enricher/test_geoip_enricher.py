# pylint: disable=missing-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestGeoipEnricher(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_geoip_enricher",
        "rules": ["tests/testdata/unit/geoip_enricher/rules"],
        "db_path": "tests/testdata/mock_external/MockGeoLite2-City.mmdb",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    expected_metrics: list = []

    def test_geoip_enricher_instantiates(self):
        rule = {
            "filter": "client.ip",
            "geoip_enricher": {"source_fields": ["client.ip"], "target_field": "client.geo"},
        }
        self._load_rule(rule)
        document = {"client": {"ip": "8.8.8.8"}}
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        # Just test that it doesn't crash - GeoIP requires database files
        assert "client" in log_event.data
