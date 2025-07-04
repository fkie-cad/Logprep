# pylint: disable=missing-module-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestTemplateReplacer(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_template_replacer",
        "rules": ["tests/testdata/unit/template_replacer/rules"],
        "template": "tests/testdata/unit/template_replacer/replacer_template.yml",
        "pattern": {
            "delimiter": "-",
            "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
            "allowed_delimiter_field": "winlog.provider_name",
            "target_field": "message",
        },
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    def setup_method(self):
        super().setup_method()
        self.object.setup()

    def test_replace_message_via_template(self):
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"test_message")

        self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2"

    def test_replace_non_existing_message_via_template(self):
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}
        log_event = LogEvent(document, original=b"test_message")

        self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2"
