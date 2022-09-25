# pylint: disable=missing-docstring
import pytest
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "writes new fields with same seperator",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} %{field2} %{field3} %{field4}"}},
        },
        {"message": "This is a message"},
        {
            "message": "This is a message",
            "field1": "This",
            "field2": "is",
            "field3": "a",
            "field4": "message",
        },
    ),
    (
        "writes new fields with different seperator",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} %{field2}:%{field3} %{field4}"}},
        },
        {"message": "This is:a message"},
        {
            "message": "This is:a message",
            "field1": "This",
            "field2": "is",
            "field3": "a",
            "field4": "message",
        },
    ),
    (
        "writes new fields with long seperator",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{field4}"}},
        },
        {"message": "This is a message"},
        {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": "message",
        },
    ),
    (
        "writes new fields and appends to existing list",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        },
        {"message": "This is a message", "field4": ["preexisting"]},
        {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": ["preexisting", "message"],
        },
    ),
    (
        "writes new fields and appends to existing empty list",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        },
        {"message": "This is a message", "field4": []},
        {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": ["message"],
        },
    ),
    (
        "writes new fields and appends to existing string",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
        },
        {"message": "This is a message", "field4": "preexisting"},
        {
            "message": "This is a message",
            "field1": "This",
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "writes new dotted fields",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {"message": "%{field1} %{my.new.field2} %{field3} %{+field4}"}
            },
        },
        {"message": "This is a message", "field4": "preexisting"},
        {
            "message": "This is a message",
            "field1": "This",
            "my": {"new": {"field2": "is"}},
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "overwrites dotted fields",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {"message": "%{field1} %{my.new.field2} %{field3} %{+field4}"}
            },
        },
        {
            "message": "This is a message",
            "field4": "preexisting",
            "my": {"new": {"field2": "preexisting"}},
        },
        {
            "message": "This is a message",
            "field1": "This",
            "my": {"new": {"field2": "is"}},
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "appends to dotted fields preexisting string",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {"message": "%{field1} %{+my.new.field2} %{field3} %{+field4}"}
            },
        },
        {
            "message": "This is a message",
            "field4": "preexisting",
            "my": {"new": {"field2": "preexisting"}},
        },
        {
            "message": "This is a message",
            "field1": "This",
            "my": {"new": {"field2": "preexisting is"}},
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "appends to dotted fields preexisting list",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {"message": "%{field1} %{+my.new.field2} %{field3} %{+field4}"}
            },
        },
        {
            "message": "This is a message",
            "field4": "preexisting",
            "my": {"new": {"field2": ["preexisting"]}},
        },
        {
            "message": "This is a message",
            "field1": "This",
            "my": {"new": {"field2": ["preexisting", "is"]}},
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "processes dotted field source",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {"message.key1.key2": "%{field1} %{field2} %{field3} %{field4}"}
            },
        },
        {"message": {"key1": {"key2": "This is the message"}}},
        {
            "message": {"key1": {"key2": "This is the message"}},
            "field1": "This",
            "field2": "is",
            "field3": "the",
            "field4": "message",
        },
    ),
]


class TestDissecter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "dissecter",
        "generic_rules": ["tests/testdata/unit/dissecter"],
        "specific_rules": ["tests/testdata/unit/dissecter"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

        # TODO add tests for multiple mappings
        # TODO add tests for convert_datatype
        # TODO add tests for ordered appending
        # TODO add tests for failures
