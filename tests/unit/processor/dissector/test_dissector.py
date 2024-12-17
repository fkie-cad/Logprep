# pylint: disable=missing-docstring

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "writes new fields with same separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{field1} %{field2} %{field3} %{field4}"}},
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
        "writes new fields with different separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{field1} %{field2}:%{field3} %{field4}"}},
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
        "writes new fields with long separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{field1} is %{field3} %{field4}"}},
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
            "dissector": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
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
            "dissector": {"mapping": {"message": "%{field1} is %{field3} %{+field4}"}},
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
            "dissector": {"mapping": {"message": "%{field1} is %{field3} %{+( )field4}"}},
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
            "dissector": {
                "mapping": {"message": "%{field1} %{my.new.field2} %{field3} %{+field4}"}
            },
        },
        {"message": "This is a message", "field4": "preexisting"},
        {
            "message": "This is a message",
            "field1": "This",
            "my": {"new": {"field2": "is"}},
            "field3": "a",
            "field4": "preexistingmessage",
        },
    ),
    (
        "overwrites dotted fields",
        {
            "filter": "message",
            "dissector": {
                "mapping": {"message": "%{field1} %{my.new.field2} %{field3} %{+( )field4}"}
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
            "dissector": {
                "mapping": {"message": "%{field1} %{+my.new.field2} %{field3} %{+( )field4}"}
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
            "my": {"new": {"field2": "preexistingis"}},
            "field3": "a",
            "field4": "preexisting message",
        },
    ),
    (
        "appends to dotted fields preexisting list",
        {
            "filter": "message",
            "dissector": {
                "mapping": {"message": "%{field1} %{+my.new.field2} %{field3} %{+( )field4}"}
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
        "processes dotted source field",
        {
            "filter": "message",
            "dissector": {
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
            "dissector": {
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
            "dissector": {
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
            "dissector": {
                "mapping": {
                    "source1": "%{+extracted.key1} %{+extracted.key2} %{+extracted.key3}",
                    "source2": "%{+( )extracted.key1} %{+( )extracted.key2} %{+( )extracted.key3}",
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
            "dissector": {
                "mapping": {
                    "message": "%{+( )extracted/4} %{+( )extracted/3} %{+( )extracted/2} %{+extracted/1}"  # pylint: disable=line-too-long
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
            "dissector": {
                "mapping": {
                    "message": "%{+( )extracted/4} %{+( )extracted/3} %{+( )extracted/2} %{+( )extracted/1}"  # pylint: disable=line-too-long
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
            "dissector": {
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
            "dissector": {
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
            "dissector": {
                "mapping": {
                    "message": "%{}: %{+( )extracted/2}",
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
        {"filter": "message", "dissector": {"convert_datatype": {"message": "int"}}},
        {"message": "42"},
        {"message": 42},
    ),
    (
        "converts datatype with mapping in dotted field notation",
        {
            "filter": "message",
            "dissector": {
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
        {"filter": "message", "dissector": {"mapping": {"message": "%{?key} %{&key}"}}},
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is the message"},
    ),
    (
        "indirect field notation: uses captured field as key and appends to it",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{?key} %{&key} %{} %{+( )&key}"}},
        },
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is message"},
    ),
    (
        "handles special chars as captured content",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{field1} %{field2} %{field3} %{+field4}"}},
        },
        {"message": "This is \\a + message"},
        {
            "message": "This is \\a + message",
            "field1": "This",
            "field2": "is",
            "field3": "\\a",
            "field4": "+ message",
        },
    ),
    (
        "handles special chars in captured content and target field names",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{~field1} %{fie ld2} %{$fie}ld3} %{+field4}"}},
        },
        {"message": "&This is\2 a mess}age /1"},
        {
            "message": "&This is\2 a mess}age /1",
            "~field1": "&This",
            "fie ld2": "is\2",
            "$fie}ld3": "a",
            "field4": "mess}age /1",
        },
    ),
    (
        "deletes source fields",
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "%{field1} %{field2} %{field3} %{field4}",
                    "message2": "%{field21} %{field22} %{field23} %{field24}",
                },
                "delete_source_fields": True,
            },
        },
        {"message": "This is a message", "message2": "This is a message"},
        {
            "field1": "This",
            "field2": "is",
            "field3": "a",
            "field4": "message",
            "field21": "This",
            "field22": "is",
            "field23": "a",
            "field24": "message",
        },
    ),
    (
        "parses path elements",
        {
            "filter": "path",
            "dissector": {
                "mapping": {
                    "path": "/%{field1}/%{field2}/%{field3}/%{field4}",
                },
            },
        },
        {"path": "/this/is/the/path"},
        {
            "path": "/this/is/the/path",
            "field1": "this",
            "field2": "is",
            "field3": "the",
            "field4": "path",
        },
    ),
    (
        "Appending without separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "INFO#%{date}#%{+date}#MOREINFO%{}"}},
        },
        {
            "message": "INFO#2022 12 06 15:12:30:534#+0100#MOREINFO",
        },
        {
            "message": "INFO#2022 12 06 15:12:30:534#+0100#MOREINFO",
            "date": "2022 12 06 15:12:30:534+0100",
        },
    ),
    (
        "Appending with special field separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": r"INFO#%{+(\()date}#%{+(\))date}#MOREINFO%{}"}},
        },
        {
            "message": "INFO#2022 12 06 15:12:30:534#+0100#MOREINFO",
        },
        {
            "message": "INFO#2022 12 06 15:12:30:534#+0100#MOREINFO",
            "date": "(2022 12 06 15:12:30:534)+0100",
        },
    ),
    (
        "Dissection with delimiter ending",
        {"filter": "message", "dissector": {"mapping": {"message": "this is %{target}."}}},
        {"message": "this is the message."},
        {"message": "this is the message.", "target": "the message"},
    ),
    (
        "Convert datatype via dissect pattern",
        {
            "filter": "message",
            "dissector": {
                "mapping": {"message": "this is %{field1|int} message and this is %{field2|bool}"}
            },
        },
        {"message": "this is 42 message and this is 0"},
        {"message": "this is 42 message and this is 0", "field1": 42, "field2": False},
    ),
    (
        "Strip char after dissecting",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "[%{time-( )}] - %{ip}"}},
        },
        {"message": "[2022-11-04 10:00:00 AM     ] - 127.0.0.1"},
        {
            "message": "[2022-11-04 10:00:00 AM     ] - 127.0.0.1",
            "time": "2022-11-04 10:00:00 AM",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip special char after dissecting",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "[%{time-(#)}] - %{ip}"}},
        },
        {"message": "[2022-11-04 10:00:00 AM####] - 127.0.0.1"},
        {
            "message": "[2022-11-04 10:00:00 AM####] - 127.0.0.1",
            "time": "2022-11-04 10:00:00 AM",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip another special char after dissecting",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "[%{time-(?)}] - %{ip}"}},
        },
        {"message": "[2022-11-04 10:00:00 AM?????] - 127.0.0.1"},
        {
            "message": "[2022-11-04 10:00:00 AM?????] - 127.0.0.1",
            "time": "2022-11-04 10:00:00 AM",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip char on both sides",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "[%{time-(*)}] - %{ip}"}},
        },
        {"message": "[***2022-11-04 10:00:00 AM***] - 127.0.0.1"},
        {
            "message": "[***2022-11-04 10:00:00 AM***] - 127.0.0.1",
            "time": "2022-11-04 10:00:00 AM",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip char while appending",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "[%{time} %{+( )time} %{+( )time-(*)}] - %{ip}"}},
        },
        {"message": "[2022-11-04 10:00:00 AM***] - 127.0.0.1"},
        {
            "message": "[2022-11-04 10:00:00 AM***] - 127.0.0.1",
            "time": "2022-11-04 10:00:00 AM",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip char while changing position",
        {
            "filter": "message",
            "dissector": {
                "mapping": {"message": "[%{time/1} %{+( )time/3} %{+( )time-(*)/2}] - %{ip}"}
            },
        },
        {"message": "[2022-11-04 10:00:00 AM***] - 127.0.0.1"},
        {
            "message": "[2022-11-04 10:00:00 AM***] - 127.0.0.1",
            "time": "2022-11-04 AM 10:00:00",
            "ip": "127.0.0.1",
        },
    ),
    (
        "Strip char in indirect field notation",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{?key} %{&key-(#)} %{} %{+( )&key-(#)}"}},
        },
        {"message": "This is## the message####"},
        {"message": "This is## the message####", "This": "is message"},
    ),
    (
        "Strip char while inferring datatype",
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "this is %{field1-(#)|int} message and this is %{field2-(#)|bool}"
                }
            },
        },
        {"message": "this is 42#### message and this is 0##"},
        {"message": "this is 42#### message and this is 0##", "field1": 42, "field2": False},
    ),
    (
        "extract end of string",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "system_%{type}"}},
        },
        {"message": "system_monitor"},
        {
            "message": "system_monitor",
            "type": "monitor",
        },
    ),
    (
        "copy field - dissect without separator",
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{sys_type}"}},
        },
        {"message": "system_monitor"},
        {
            "message": "system_monitor",
            "sys_type": "system_monitor",
        },
    ),
    (
        "ignore missing fields",
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "%{sys_type}",
                    "does_not_exist": "%{sys_type}",
                },
                "ignore_missing_fields": True,
            },
        },
        {"message": "system_monitor"},
        {
            "message": "system_monitor",
            "sys_type": "system_monitor",
        },
    ),
]
failure_test_cases = [  # testcase, rule, event, expected
    (
        "Tags failure if convert is not possible",
        {
            "filter": "message",
            "dissector": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I can't be converted into int"},
        {
            "message": "I can't be converted into int",
            "tags": ["_dissector_failure"],
        },
    ),
    (
        "Tags failure if convert is not possible and extends tags list",
        {
            "filter": "message",
            "dissector": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I can't be converted into int", "tags": ["preexisting"]},
        {
            "message": "I can't be converted into int",
            "tags": ["_dissector_failure", "preexisting"],
        },
    ),
    (
        "Tags custom failure if convert is not possible",
        {
            "filter": "message",
            "dissector": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag_2"],
            },
        },
        {"message": "I can't be converted into int"},
        {
            "message": "I can't be converted into int",
            "tags": ["custom_tag_1", "custom_tag_2"],
        },
    ),
    (
        "Tags custom failure if convert is not possible and extends tag list",
        {
            "filter": "message",
            "dissector": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag_2"],
            },
        },
        {"message": "I can't be converted into int", "tags": ["preexisting1", "preexisting2"]},
        {
            "message": "I can't be converted into int",
            "tags": ["custom_tag_1", "custom_tag_2", "preexisting1", "preexisting2"],
        },
    ),
    (
        "Tags failure if mapping field does not exist",
        {"filter": "message", "dissector": {"mapping": {"doesnotexist": "%{} %{}"}}},
        {"message": "This is the message which does not matter"},
        {"message": "This is the message which does not matter", "tags": ["_dissector_failure"]},
    ),
]


class TestDissector(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "dissector",
        "rules": ["tests/testdata/unit/dissector/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert event == expected, testcase
