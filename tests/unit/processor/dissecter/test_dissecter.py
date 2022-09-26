# pylint: disable=missing-docstring
import pytest
from tests.unit.processor.base import BaseProcessorTestCase
from logprep.processor.base.exceptions import ProcessingWarning

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
    (
        "processes multiple mappings to different target fields",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "source1": "%{extracted.source1.key1} %{extracted.source1.key2} %{extracted.source1.key3}",  # pylint: disable=line-too-long
                    "source2": "%{extracted.source2.key1} %{extracted.source2.key2} %{extracted.source2.key3}",  # pylint: disable=line-too-long
                }
            },
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
            "extracted": {
                "source1": {"key1": "This", "key2": "is", "key3": "source1"},
                "source2": {"key1": "This", "key2": "is", "key3": "source2"},
            },
        },
    ),
    (
        "processes multiple mappings to same target fields (overwrite)",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "source1": "%{extracted.key1} %{extracted.key2} %{extracted.key3}",
                    "source2": "%{extracted.key1} %{extracted.key2} %{extracted.key3}",
                }
            },
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
            "extracted": {"key1": "This", "key2": "is", "key3": "source2"},
        },
    ),
    (
        "processes multiple mappings to same target fields (appending)",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "source1": "%{+extracted.key1} %{+extracted.key2} %{+extracted.key3}",
                    "source2": "%{+extracted.key1} %{+extracted.key2} %{+extracted.key3}",
                }
            },
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
        },
        {
            "message": "This message does not matter",
            "source1": "This is source1",
            "source2": "This is source2",
            "extracted": {"key1": "This This", "key2": "is is", "key3": "source1 source2"},
        },
    ),
    (
        "append to new field in different order as string",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{+extracted/4} %{+extracted/3} %{+extracted/2} %{+extracted/1}"
                }
            },
        },
        {"message": "This is the message"},
        {"message": "This is the message", "extracted": "message the is This"},
    ),
    (
        "append to existing field in different order as string",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{+extracted/4} %{+extracted/3} %{+extracted/2} %{+extracted/1}"
                }
            },
        },
        {"message": "This is the message", "extracted": "preexisting"},
        {"message": "This is the message", "extracted": "preexisting message the is This"},
    ),
    (
        "append to existing empty list field in different order as list",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{+extracted/4} %{+extracted/3} %{+extracted/2} %{+extracted/1}"
                }
            },
        },
        {"message": "This is the message", "extracted": []},
        {"message": "This is the message", "extracted": ["message", "the", "is", "This"]},
    ),
    (
        "append to existing prefilled field in different order as list",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{+extracted/4} %{+extracted/3} %{+extracted/2} %{+extracted/1}"
                }
            },
        },
        {"message": "This is the message", "extracted": ["preexisting"]},
        {
            "message": "This is the message",
            "extracted": ["preexisting", "message", "the", "is", "This"],
        },
    ),
    (
        "append to new field in specified order as string with multiple fields",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{}: %{+extracted/2}",
                    "message2": "%{}: %{+extracted/1}",
                }
            },
        },
        {"message": "The first message: first", "message2": "The second message: second"},
        {
            "message": "The first message: first",
            "message2": "The second message: second",
            "extracted": "second first",
        },
    ),
    (
        "converts datatype without mapping",
        {"filter": "message", "dissecter": {"convert_datatype": {"message": "int"}}},
        {"message": "42"},
        {"message": 42},
    ),
    (
        "converts datatype with mapping in dotted field notation",
        {
            "filter": "message",
            "dissecter": {
                "mapping": {
                    "message": "%{}of %{extracted.message_float} and a int of %{extracted.message_int}"  # pylint: disable=line-too-long
                },
                "convert_datatype": {
                    "extracted.message_int": "int",
                    "extracted.message_float": "float",
                },
            },
        },
        {"message": "This message has a float of 1.23 and a int of 1337"},
        {
            "message": "This message has a float of 1.23 and a int of 1337",
            "extracted": {"message_float": 1.23, "message_int": 1337},
        },
    ),
    (
        "indirect field notation: uses captured field as key",
        {"filter": "message", "dissecter": {"mapping": {"message": "%{?key} %{&key}"}}},
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is the message"},
    ),
    (
        "indirect field notation: uses captured field as key and append to it",
        {
            "filter": "message",
            "dissecter": {"mapping": {"message": "%{?key} %{&key} %{} %{+&key}"}},
        },
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is message"},
    ),
]
failure_test_cases = [  # testcase, rule, event, expected
    (
        "Tags failure if convert is not possible",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I cant't be converted into int"},
        {
            "message": "I cant't be converted into int",
            "tags": ["_dissectfailure"],
        },
    ),
    (
        "Tags failure if convert is not possible and extends tags list",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I cant't be converted into int", "tags": ["preexisting"]},
        {
            "message": "I cant't be converted into int",
            "tags": ["preexisting", "_dissectfailure"],
        },
    ),
    (
        "Tags custom failure if convert is not possible",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag2"],
            },
        },
        {"message": "I cant't be converted into int"},
        {
            "message": "I cant't be converted into int",
            "tags": ["custom_tag_1", "custom_tag2"],
        },
    ),
    (
        "Tags custom failure if convert is not possible and extends tag list",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag2"],
            },
        },
        {"message": "I cant't be converted into int", "tags": ["preexisting1", "preexisting2"]},
        {
            "message": "I cant't be converted into int",
            "tags": ["preexisting1", "preexisting2", "custom_tag_1", "custom_tag2"],
        },
    ),
    (
        "Tags  failure if mapping field does not exist",
        {"filter": "message", "dissecter": {"mapping": {"doesnotexist": "%{} %{}"}}},
        {"message": "This is the message which does not matter"},
        {"message": "This is the message which does not matter", "tags": ["_dissectfailure"]},
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

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected
