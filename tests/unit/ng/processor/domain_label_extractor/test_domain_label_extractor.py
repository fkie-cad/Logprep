# pylint: disable=protected-access
# pylint: disable=missing-docstring


from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestDomainLabelExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_domain_label_extractor",
        "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    def test_domain_extraction_from_full_url(self):
        document = {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}}
        expected_output = {
            "url": {
                "domain": "https://url.full.domain.de/path/file?param=1",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "url.full",
            }
        }
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected_output

    def test_domain_extraction_to_existing_field(self):
        document = {"url": {"domain": "www.test.domain.de"}}
        expected_output = {
            "url": {
                "domain": "www.test.domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "www.test",
            }
        }
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected_output
