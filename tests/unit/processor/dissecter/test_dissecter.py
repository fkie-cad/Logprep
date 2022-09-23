# pylint: disable=missing-docstring
from tests.unit.processor.base import BaseProcessorTestCase


class TestDissecter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "dissecter",
        "generic_rules": ["tests/testdata/unit/dissecter"],
        "specific_rules": ["tests/testdata/unit/dissecter"],
    }

    def test_process_writes_new_fields_with_same_seperator(self):
        event = {"message": "This is a message"}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} %{field2} %{field3} %{field4}"}},
        }
        expected = {
            "message": "This is a message",
            "field1": "This",
            "field2": "is",
            "field3": "a",
            "field4": "message",
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected
