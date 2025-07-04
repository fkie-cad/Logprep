# pylint: disable=missing-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestGrokker(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_grokker",
        "rules": ["tests/testdata/unit/grokker/rules"],
    }

    expected_metrics: list = []

    def test_grokker_instantiates(self):
        rule = {
            "filter": "message",
            "grokker": {"mapping": {"message": "%{WORD:first_word} %{GREEDYDATA:rest}"}},
        }
        self._load_rule(rule)
        document = {"message": "hello world"}
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data["message"] == "hello world"
