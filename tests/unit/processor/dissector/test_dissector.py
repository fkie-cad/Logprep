# pylint: disable=missing-docstring
# pylint: disable=duplicate-code
import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [
    pytest.param(
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
        id="writes new fields with same separator",
    ),
    pytest.param(
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
        id="writes new fields with different separator",
    ),
    pytest.param(
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
        id="writes new fields with long separator",
    ),
    pytest.param(
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
        id="writes new fields and appends to existing list",
    ),
    pytest.param(
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
        id="writes new fields and appends to existing empty list",
    ),
    pytest.param(
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
        id="writes new fields and appends to existing string",
    ),
    pytest.param(
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
        id="writes new dotted fields",
    ),
    pytest.param(
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
        id="overwrites dotted fields",
    ),
    pytest.param(
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
        id="appends to dotted fields preexisting string",
    ),
    pytest.param(
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
        id="appends to dotted fields preexisting list",
    ),
    pytest.param(
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
        id="processes dotted source field",
    ),
    pytest.param(
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
        id="processes multiple mappings to different target fields",
    ),
    pytest.param(
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
        id="processes multiple mappings to same target fields (overwrite)",
    ),
    pytest.param(
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
        id="processes multiple mappings to same target fields (appending)",
    ),
    pytest.param(
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
        id="append to new field in different order as string",
    ),
    pytest.param(
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
        id="append to existing field in different order as string",
    ),
    pytest.param(
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
        id="append to existing empty list field in different order as list",
    ),
    pytest.param(
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
        id="append to existing prefilled field in different order as list",
    ),
    pytest.param(
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
        id="append to new field in specified order as string with multiple fields",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"convert_datatype": {"message": "int"}}},
        {"message": "42"},
        {"message": 42},
        id="converts datatype without mapping",
    ),
    pytest.param(
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
        id="converts datatype with mapping in dotted field notation",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{?key} %{&key}"}}},
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is the message"},
        id="indirect field notation: uses captured field as key",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{?key} %{&key} %{} %{+( )&key}"}},
        },
        {"message": "This is the message"},
        {"message": "This is the message", "This": "is message"},
        id="indirect field notation: uses captured field as key and appends to it",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{field1} %{field2} %{field3} %{+field4}"}},
        },
        {"message": "This is \\a + mess}age"},
        {
            "message": "This is \\a + mess}age",
            "field1": "This",
            "field2": "is",
            "field3": "\\a",
            "field4": "+ mess}age",
        },
        id="handles special chars as captured content",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "%{~field1} %{fie ld2} %{field3} %{field\\.4} %{+field\\\\5}"
                }
            },
        },
        {"message": "&This is\2 mess}a\3ge /4 /5"},
        {
            "message": "&This is\2 mess}a\3ge /4 /5",
            "~field1": "&This",
            "fie ld2": "is\2",
            "field3": "mess}a\3ge",
            "field.4": "/4",
            "field\\5": "/5",
        },
        id="handles escaping of dotted notation in captured content and target field names",
    ),
    pytest.param(
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
        id="deletes source fields",
    ),
    pytest.param(
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
        id="parses path elements",
    ),
    pytest.param(
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
        id="Appending without separator",
    ),
    pytest.param(
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
        id="Appending with special field separator",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "this is %{target}."}}},
        {"message": "this is the message."},
        {"message": "this is the message.", "target": "the message"},
        id="Dissection with delimiter ending",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {
                "mapping": {"message": "this is %{field1|int} message and this is %{field2|bool}"}
            },
        },
        {"message": "this is 42 message and this is 0"},
        {"message": "this is 42 message and this is 0", "field1": 42, "field2": False},
        id="Convert datatype via dissect pattern",
    ),
    pytest.param(
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
        id="Strip char after dissecting",
    ),
    pytest.param(
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
        id="Strip special char after dissecting",
    ),
    pytest.param(
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
        id="Strip another special char after dissecting",
    ),
    pytest.param(
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
        id="Strip char on both sides",
    ),
    pytest.param(
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
        id="Strip char while appending",
    ),
    pytest.param(
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
        id="Strip char while changing position",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{?key} %{&key-(#)} %{} %{+( )&key-(#)}"}},
        },
        {"message": "This is## the message####"},
        {"message": "This is## the message####", "This": "is message"},
        id="Strip char in indirect field notation",
    ),
    pytest.param(
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
        id="Strip char while inferring datatype",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "system_%{type}"}},
        },
        {"message": "system_monitor"},
        {
            "message": "system_monitor",
            "type": "monitor",
        },
        id="extract end of string",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{sys_type}"}},
        },
        {"message": "system_monitor"},
        {
            "message": "system_monitor",
            "sys_type": "system_monitor",
        },
        id="copy field - dissect without separator",
    ),
    pytest.param(
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
        id="ignore missing fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "proxy{addr=%{destination.address}}",
                },
            },
        },
        {"message": "proxy{addr=10.99.172.10:4191}"},
        {
            "destination": {
                "address": "10.99.172.10:4191",
            },
            "message": "proxy{addr=10.99.172.10:4191}",
        },
        id="handle curly braces in message simple case",
    ),
    pytest.param(
        {
            "filter": "message",
            "dissector": {
                "mapping": {
                    "message": "proxy{addr=%{destination.address}}:service{ns=linkerd-multicluster "
                    "name=%{destination.domain} "
                    "port=4191}:endpoint{addr=%{source.address}}: %{log.logger}: %{message}",
                },
            },
        },
        {
            "message": "proxy{addr=10.99.172.10:4191}:service{ns=linkerd-multicluster "
            "name=probe-gateway-bbb port=4191}:endpoint{addr=192.8.177.98:4191}: "
            "linkerd_reconnect: Failed to connect error=connect timed out after 1s"
        },
        {
            "destination": {
                "address": "10.99.172.10:4191",
                "domain": "probe-gateway-bbb",
            },
            "log": {
                "logger": "linkerd_reconnect",
            },
            "message": "Failed to connect error=connect timed out after 1s",
            "source": {
                "address": "192.8.177.98:4191",
            },
        },
        id="handle curly braces in message full case",
    ),
]
failure_test_cases = [
    pytest.param(
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
        id="Tags failure if convert is not possible",
    ),
    pytest.param(
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
        id="Tags failure if convert is not possible and extends tags list",
    ),
    pytest.param(
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
        id="Tags custom failure if convert is not possible",
    ),
    pytest.param(
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
        id="Tags custom failure if convert is not possible and extends tag list",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"doesnotexist": "%{} %{}"}}},
        {"message": "This is the message which does not matter"},
        {"message": "This is the message which does not matter", "tags": ["_dissector_failure"]},
        id="Tags failure if mapping field does not exist",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{&key} %{?key}"}}},
        {"message": "This is the message"},
        {"message": "This is the message", "tags": ["_dissector_failure"]},
        id="indirect field notation in wrong order",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": 1337},
        {"message": 1337, "tags": ["_dissector_failure"]},
        id="non-supported int message",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": 42.42},
        {"message": 42.42, "tags": ["_dissector_failure"]},
        id="unexpected float message",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": True},
        {"message": True, "tags": ["_dissector_failure"]},
        id="unexpected bool message",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": None},
        {"message": None, "tags": ["_dissector_failure"]},
        id="unexpected None message",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": ["abc"]},
        {"message": ["abc"], "tags": ["_dissector_failure"]},
        id="unexpected list message",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": 1337},
        {"message": 1337, "tags": ["_dissector_failure"]},
        id="non-string value type",
    ),
    pytest.param(
        {"filter": "message", "dissector": {"mapping": {"message": "%{key}"}}},
        {"message": {"key": "value"}},
        {"message": {"key": "value"}, "tags": ["_dissector_failure"]},
        id="unexpected dict message",
    ),
]


class TestDissector(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "dissector",
        "rules": ["tests/testdata/unit/dissector/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert event == expected
