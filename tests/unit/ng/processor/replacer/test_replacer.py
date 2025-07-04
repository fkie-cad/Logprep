# pylint: disable=missing-docstring

import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestReplacer(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_replacer",
        "rules": ["tests/testdata/unit/replacer/rules_2"],
    }

    def test_replace_simple_string(self):
        rule = {
            "filter": "message",
            "replacer": {
                "mapping": {
                    "message": "This is %{*} text"
                },
                "target_field": "new_message"
            }
        }
        document = {"message": "This is old text"}
        expected = {"message": "This is old text", "new_message": "This is old text"}
        
        self._load_rule(rule)
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == expected
