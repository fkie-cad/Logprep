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

    def test_process_writes_new_fields_with_different_seperator(self):
        event = {"message": "This is:a message"}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} %{field2}:%{field3} %{field4}"}},
        }
        expected = {
            "message": "This is:a message",
            "field1": "This",
            "field2": "is",
            "field3": "a",
            "field4": "message",
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_process_writes_new_fields_with_long_seperator(self):
        event = {"message": "This is a message"}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{field4}"}},
        }
        expected = {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": "message",
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_process_writes_new_fields_and_appends_to_existing_list(self):
        event = {"message": "This is a message", "field4": ["preexisting"]}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        }
        expected = {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": ["preexisting", "message"],
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_process_writes_new_fields_and_appends_to_existing_empty_list(self):
        event = {"message": "This is a message", "field4": []}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        }
        expected = {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": ["message"],
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_process_writes_new_fields_and_appends_to_existing_string(self):
        event = {"message": "This is a message", "field4": "preexisting"}
        rule = {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        }
        expected = {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": "preexisting message",
        }
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

        # TODO add tests for multiple mappings
        # TODO add tests for dotted fields with strings
        # TODO add tests for dotted fields with lists
        # TODO add tests for convert_datatype
        # TODO add tests for ordered appending
        # TODO add tests for failures
