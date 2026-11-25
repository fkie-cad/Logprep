# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-lines
# pylint: disable=too-many-arguments,too-many-positional-arguments
import json

import pytest

from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    ProcessingError,
    ProcessingWarning,
)
from logprep.processor.decoder.decoders.logfmt import parse_logfmt
from logprep.processor.decoder.decoders.registry import get_decoder
from logprep.processor.decoder.decoders.windows_event_log import MAX_XML_DEPTH
from logprep.util.typing import is_list_of
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

WINDOWS_EVENT_FIELDS = {
    "SourceName": "Microsoft-Windows-Security-Auditing",
    "ProviderGuid": "{54849625-5478-4994-a5ba-3e3b0328c30d}",
    "EventID": 4768,
    "Version": 2,
    "LevelValue": 0,
    "TaskValue": 14339,
    "OpcodeValue": 0,
    "Keywords": "0x8010000000000000",
    "EventTime": "2026-11-12T13:13:57.811161+00:00",
    "RecordNumber": 17115866894,
    "ActivityID": "{B32E47DD-4C50-0007-0B48-2EB3504CDD01}",
    "ExecutionProcessID": 144,
    "ExecutionThreadID": 3480,
    "Channel": "Security",
    "Hostname": "Z00WHVDC01.bbb.local",
    "TargetUserName": "z000sms03s",
    "TargetDomainName": "ITB",
    "Status": "0x12",
}
MINIMAL_WINDOWS_EVENT_FIELDS = {
    "Channel": "Application",
    "EventTime": "2026-10-14T10:55:07.744922+00:00",
}
CUSTOM_XMLFIELDS = {
    "EventID": {"convert": "str"},
    "SourceName": {"attribute": "Guid"},
    "Channel": {"element": "Computer"},
    "TargetUserName": {"element": "Data", "section": "EventData", "name": "TargetDomainName"},
    "User": {"element": "Data", "section": "EventData", "name": "TargetUserName"},
}

example_test_cases = [
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {"message": '{"to_decode": "decode value"}'},
        {
            "message": '{"to_decode": "decode value"}',
            "new_field": {"to_decode": "decode value"},
        },
        id="decodes simple json to target field",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {"message": '{"to.decode": "decode value"}'},
        {
            "message": '{"to.decode": "decode value"}',
            "new_field": {"to.decode": "decode value"},
        },
        id="decodes simple json to target field dotted",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "source_format": "base64",
            },
        },
        {"message": "dGhpcyxpcyx0aGUsbWVzc2FnZQ=="},
        {"message": "dGhpcyxpcyx0aGUsbWVzc2FnZQ==", "new_field": "this,is,the,message"},
        id="decodes simple base64",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "clf",
                "overwrite_target": True,
            },
        },
        {
            "message": '127.0.0.1 ident alice [01/May/2025:07:20:10 +0000] "GET /index.html HTTP/1.1" 200 9481',
        },
        {
            "message": '127.0.0.1 ident alice [01/May/2025:07:20:10 +0000] "GET /index.html HTTP/1.1" 200 9481',
            "parsed": {
                "host": "127.0.0.1",
                "ident": "ident",
                "authuser": "alice",
                "timestamp": "01/May/2025:07:20:10 +0000",
                "request_line": "GET /index.html HTTP/1.1",
                "status": "200",
                "bytes": "9481",
            },
        },
        id="parse clf",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "nginx",
                "overwrite_target": True,
            },
        },
        {
            "message": '192.168.32.9 - - [19/Dec/2023:14:04:42 +0000]  200 "POST /otlp/v1/metrics HTTP/1.1" 0 "-" "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)" "-"'
        },
        {
            "message": '192.168.32.9 - - [19/Dec/2023:14:04:42 +0000]  200 "POST /otlp/v1/metrics HTTP/1.1" 0 "-" "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)" "-"',
            "parsed": {
                "agent": "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)",
                "code": "200",
                "gzip_ratio": "-",
                "host": "192.168.32.9",
                "method": "POST",
                "path": "/otlp/v1/metrics",
                "referer": "-",
                "size": "0",
                "time": "19/Dec/2023:14:04:42 +0000",
                "user": "-",
            },
        },
        id="parse nginx",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc3164",
                "overwrite_target": True,
            },
        },
        {
            "message": "<34>Oct 3 10:15:32 mymachine su[12345]: 'su root' failed for user on /dev/pts/0"
        },
        {
            "message": "<34>Oct 3 10:15:32 mymachine su[12345]: 'su root' failed for user on /dev/pts/0",
            "parsed": {
                "host": "mymachine",
                "ident": "su",
                "message": "'su root' failed for user on /dev/pts/0",
                "pid": "12345",
                "pri": "34",
                "time": "Oct 3 10:15:32",
            },
        },
        id="parse syslog rfc 3164",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc3164_local",
                "overwrite_target": True,
            },
        },
        {"message": "<34>Oct 3 10:15:32 su[12345]: 'su root' failed for user on /dev/pts/0"},
        {
            "message": "<34>Oct 3 10:15:32 su[12345]: 'su root' failed for user on /dev/pts/0",
            "parsed": {
                "ident": "su",
                "message": "'su root' failed for user on /dev/pts/0",
                "pid": "12345",
                "pri": "34",
                "time": "Oct 3 10:15:32",
            },
        },
        id="parse syslog rfc 3164 local",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc5424",
                "overwrite_target": True,
            },
        },
        {
            "message": "<34>1 2025-01-03T14:07:15.003Z mymachine.example.com su 12345 ID47 - 'su root' failed for user on /dev/pts/0"
        },
        {
            "message": "<34>1 2025-01-03T14:07:15.003Z mymachine.example.com su 12345 ID47 - 'su root' failed for user on /dev/pts/0",
            "parsed": {
                "host": "mymachine.example.com",
                "ident": "su",
                "pid": "12345",
                "message": "'su root' failed for user on /dev/pts/0",
                "pri": "34",
                "time": "2025-01-03T14:07:15.003Z",
                "msgid": "ID47",
                "extradata": "-",
            },
        },
        id="parse syslog rfc 5424",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "logfmt",
                "overwrite_target": True,
            },
        },
        {"message": 'level=INFO host=Ubuntu msg="Connected to PostgreSQL database"'},
        {
            "message": 'level=INFO host=Ubuntu msg="Connected to PostgreSQL database"',
            "parsed": {
                "host": "Ubuntu",
                "level": "INFO",
                "msg": "Connected to PostgreSQL database",
            },
        },
        id="parse logfmt",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "cri",
                "overwrite_target": True,
            },
        },
        {"message": "2019-04-30T02:12:41.8443515Z stdout F message"},
        {
            "message": "2019-04-30T02:12:41.8443515Z stdout F message",
            "parsed": {
                "stream": "stdout",
                "flags": "F",
                "message": "message",
                "timestamp": "2019-04-30T02:12:41.8443515Z",
            },
        },
        id="parse cri",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "docker",
                "overwrite_target": True,
            },
        },
        {
            "message": '{"log":"log message","stream":"stderr","time":"2019-04-30T02:12:41.8443515Z"}'
        },
        {
            "message": '{"log":"log message","stream":"stderr","time":"2019-04-30T02:12:41.8443515Z"}',
            "parsed": {
                "stream": "stderr",
                "output": "log message",
                "timestamp": "2019-04-30T02:12:41.8443515Z",
            },
        },
        id="parse docker",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "message"},
                "source_format": "decolorize",
                "overwrite_target": True,
            },
        },
        {
            "message": "ls\r\n\x1b[00m\x1b[01;31mexamplefile.zip\x1b[00m\r\n\x1b[01;31m",
        },
        {
            "message": "ls\r\nexamplefile.zip\r\n",
        },
        id="decolorize simple",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            )
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            ),
            "parsed": WINDOWS_EVENT_FIELDS,
        },
        id="parse windows event log into flat dict",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "parsed",
                "source_format": "windows_event_log",
                "delete_source_fields": True,
            },
        },
        {
            "message": (
                "<Event><System><!-- generated --><Channel>Application</Channel>"
                '<TimeCreated SystemTime="2026-10-14T12:55:07.744922+02:00"/></System></Event>'
            )
        },
        {"parsed": MINIMAL_WINDOWS_EVENT_FIELDS},
        id="parse minimal windows event log without namespace",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                '<Event><System><EventID>not-a-number</EventID><TimeCreated SystemTime="not-a-time"/>'
                "<Version/></System>"
                '<EventData><Data Name="Empty"></Data></EventData></Event>'
            )
        },
        {
            "message": (
                '<Event><System><EventID>not-a-number</EventID><TimeCreated SystemTime="not-a-time"/>'
                "<Version/></System>"
                '<EventData><Data Name="Empty"></Data></EventData></Event>'
            ),
            "parsed": {
                "EventID": "not-a-number",
                "EventTime": "not-a-time",
            },
        },
        id="parse windows event log with unparsable values",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><Version/></System>"
                '<EventData><Data Name="EmptyData"></Data><Data Name="Present">ok</Data>'
                "<Data></Data></EventData></Event>"
            )
        },
        {
            "message": (
                "<Event><System><Version/></System>"
                '<EventData><Data Name="EmptyData"></Data><Data Name="Present">ok</Data>'
                "<Data></Data></EventData></Event>"
            ),
            "parsed": {"Present": "ok"},
        },
        id="parse windows event log skips empty values in system and data fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><EventID>2</EventID></System>"
                '<UserData><Data Name="Param1">a</Data></UserData>'
                '<ProcessingErrorData><Data Name="ErrorCode">5</Data></ProcessingErrorData></Event>'
            )
        },
        {
            "message": (
                "<Event><System><EventID>2</EventID></System>"
                '<UserData><Data Name="Param1">a</Data></UserData>'
                '<ProcessingErrorData><Data Name="ErrorCode">5</Data></ProcessingErrorData></Event>'
            ),
            "parsed": {
                "EventID": 2,
                "Param1": "a",
                "ErrorCode": "5",
            },
        },
        id="parse windows event log with user and processing error data",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><EventID>2</EventID></System>"
                '<EventData><Data Name="Param1">from_event</Data></EventData>'
                '<UserData><Data Name="Param1">from_user</Data></UserData>'
                '<ProcessingErrorData><Data Name="ErrorCode">5</Data></ProcessingErrorData></Event>'
            )
        },
        {
            "message": (
                "<Event><System><EventID>2</EventID></System>"
                '<EventData><Data Name="Param1">from_event</Data></EventData>'
                '<UserData><Data Name="Param1">from_user</Data></UserData>'
                '<ProcessingErrorData><Data Name="ErrorCode">5</Data></ProcessingErrorData></Event>'
            ),
            "parsed": {
                "EventID": 2,
                "Param1": "from_event",
                "ErrorCode": "5",
            },
        },
        id="parse windows event log does not overwrite data field",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "message"},
                "source_format": "windows_event_log",
                "overwrite_target": True,
            },
        },
        {
            "message": (
                "<Event><System><!-- generated --><Channel>Application</Channel>"
                '<TimeCreated SystemTime="2026-10-14T12:55:07.744922+02:00"/></System></Event>'
            )
        },
        {"message": MINIMAL_WINDOWS_EVENT_FIELDS},
        id="overwrite source field with parsed windows event log",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {},
            },
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            )
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            ),
            "parsed": WINDOWS_EVENT_FIELDS,
        },
        id="empty xmlfields keeps the default extraction",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {
                    "EventXML": {"element": "Data", "section": "EventData", "name": "Param1"}
                },
            },
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                '<EventData><Data Name="Param1">value</Data></EventData></Event>'
            )
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                '<EventData><Data Name="Param1">value</Data></EventData></Event>'
            ),
            "parsed": {"EventID": 1, "Param1": "value", "EventXML": "value"},
        },
        id="xmlfields can target EventXML",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": CUSTOM_XMLFIELDS,
            },
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            )
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            ),
            "parsed": {
                **WINDOWS_EVENT_FIELDS,
                "SourceName": "{54849625-5478-4994-a5ba-3e3b0328c30d}",
                "EventID": "4768",
                "Channel": "Z00WHVDC01.bbb.local",
                "TargetUserName": "ITB",
                "User": "z000sms03s",
            },
        },
        id="xmlfields are merged into the default extraction",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {
                    "EventVersion": {
                        "element": "Event",
                        "section": "Event",
                        "attribute": "Version",
                    }
                },
            },
        },
        {"message": '<Event Version="1"><System><Channel>Application</Channel></System></Event>'},
        {
            "message": '<Event Version="1"><System><Channel>Application</Channel></System></Event>',
            "parsed": {
                "Channel": "Application",
                "EventVersion": "1",
            },
        },
        id="xmlfields read root attributes next to defaults",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {
                    "Code": {
                        "element": "Data",
                        "section": "UserData",
                        "name": "Code",
                        "convert": "int",
                    }
                },
            },
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                '<UserData><Wrapper><Data Name="Code">7</Data></Wrapper></UserData></Event>'
            )
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                '<UserData><Wrapper><Data Name="Code">7</Data></Wrapper></UserData></Event>'
            ),
            "parsed": {
                "EventID": 1,
                "Code": 7,
            },
        },
        id="xmlfields find nested data elements by name next to defaults",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {
                    "Data": {"element": "Data", "section": "UserData"},
                    "Unknown": {
                        "element": "Data",
                        "section": "EventData",
                        "name": "Unknown",
                    },
                },
            },
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            )
        },
        {
            "message": (
                '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                "<System>"
                '<Provider Name="Microsoft-Windows-Security-Auditing" '
                'Guid="{54849625-5478-4994-a5ba-3e3b0328c30d}"/>'
                "<EventID>4768</EventID>"
                "<Version>2</Version>"
                "<Level>0</Level>"
                "<Task>14339</Task>"
                "<Opcode>0</Opcode>"
                "<Keywords>0x8010000000000000</Keywords>"
                '<TimeCreated SystemTime="2026-11-12T13:13:57.811161100Z"/>'
                "<EventRecordID>17115866894</EventRecordID>"
                '<Correlation ActivityID="{B32E47DD-4C50-0007-0B48-2EB3504CDD01}"/>'
                '<Execution ProcessID="144" ThreadID="3480"/>'
                "<Channel>Security</Channel>"
                "<Computer>Z00WHVDC01.bbb.local</Computer>"
                "<Security/>"
                "</System>"
                "<EventData>"
                '<Data Name="TargetUserName">z000sms03s</Data>'
                '<Data Name="TargetDomainName">ITB</Data>'
                '<Data Name="Status">0x12</Data>'
                '<Data Name="CertIssuerName"></Data>'
                "</EventData>"
                "</Event>"
            ),
            "parsed": WINDOWS_EVENT_FIELDS,
        },
        id="xmlfields skip missing sections and unmatched names",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": {
                    "ActivityID": {"element": "Correlation", "attribute": "ActivityID"},
                    "EventTime": {
                        "element": "TimeCreated",
                        "attribute": "SystemTime",
                        "convert": "timestamp",
                    },
                    "EventID": {"convert": "int"},
                },
            },
        },
        {
            "message": "<Event><System><Correlation/><TimeCreated/><EventID>42</EventID></System></Event>"
        },
        {
            "message": "<Event><System><Correlation/><TimeCreated/><EventID>42</EventID></System></Event>",
            "parsed": {"EventID": 42},
        },
        id="xmlfields with missing attributes are skipped",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "json_message OR escaped_message",
            "decoder": {
                "mapping": {
                    "json_message": "json_field",
                    "escaped_message": "escaped_field",
                }
            },
        },
        {
            "escaped_message": '{"to_decode": "decode value"}',
            "json_message": '{"json_decode": "json_value"}',
        },
        {
            "escaped_message": '{"to_decode": "decode value"}',
            "json_message": '{"json_decode": "json_value"}',
            "json_field": {"json_decode": "json_value"},
            "escaped_field": {"to_decode": "decode value"},
        },
        id="decodes json with mapping to corresponding target fields",
    ),
    pytest.param(
        {
            "filter": "json\\.message OR escaped\\.message",
            "decoder": {
                "mapping": {
                    "json\\.message": "json\\.field",
                    "escaped\\.message": "escaped\\.field",
                }
            },
        },
        {
            "escaped.message": '{"to.decode": "decode value"}',
            "json.message": '{"json.decode": "json.value"}',
        },
        {
            "escaped.message": '{"to.decode": "decode value"}',
            "json.message": '{"json.decode": "json.value"}',
            "json.field": {"json.decode": "json.value"},
            "escaped.field": {"to.decode": "decode value"},
        },
        id="decodes json with mapping to corresponding target fields - dotted",
    ),
    pytest.param(
        {
            "filter": "json\\.message\\\\ OR escaped\\.message\\\\",
            "decoder": {
                "mapping": {
                    "json\\.message\\\\": "json\\.field\\\\",
                    "escaped\\.message\\\\": "escaped\\.field\\\\",
                }
            },
        },
        {
            "escaped.message\\": '{"to.decode": "decode value"}',
            "json.message\\": '{"json.decode": "json.value"}',
        },
        {
            "escaped.message\\": '{"to.decode": "decode value"}',
            "json.message\\": '{"json.decode": "json.value"}',
            "json.field\\": {"json.decode": "json.value"},
            "escaped.field\\": {"to.decode": "decode value"},
        },
        id="decodes json with mapping to corresponding target fields - dotted and backslashes",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "source_format": "base64",
                "delete_source_fields": True,
            },
        },
        {"message": "dGhpcyxpcyx0aGUsbWVzc2FnZQ=="},
        {"new_field": "this,is,the,message"},
        id="decodes simple base64 and removes source field",
    ),
    pytest.param(
        {
            "filter": "message1",
            "decoder": {
                "mapping": {"message1": "new_field1", "message2": "new_field2"},
                "source_format": "base64",
                "delete_source_fields": True,
            },
        },
        {
            "message1": "dGhpcyxpcyx0aGUsbWVzc2FnZQ==",
            "message2": "dGhpcyxpcyx0aGUsbWVzc2FnZQ==",
        },
        {"new_field1": "this,is,the,message", "new_field2": "this,is,the,message"},
        id="decodes simple base64 and removes source fields with mapping",
    ),
    pytest.param(
        {
            "filter": "message1",
            "decoder": {
                "mapping": {"message1": "message1", "message2": "message2"},
                "source_format": "base64",
                "overwrite_target": True,
            },
        },
        {
            "message1": "dGhpcyxpcyx0aGUsbWVzc2FnZQ==",
            "message2": "dGhpcyxpcyx0aGUsbWVzc2FnZQ==",
        },
        {"message1": "this,is,the,message", "message2": "this,is,the,message"},
        id="decodes simple base64 and overwrites source fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "nginx",
                "overwrite_target": True,
            },
        },
        {
            "message": '192.168.16.37 - - [19/Dec/2023:14:04:39 +0000]  200 "GET / HTTP/1.1" 2 "-" "kube-probe/1.32+" "-"'
        },
        {
            "message": '192.168.16.37 - - [19/Dec/2023:14:04:39 +0000]  200 "GET / HTTP/1.1" 2 "-" "kube-probe/1.32+" "-"',
            "parsed": {
                "agent": "kube-probe/1.32+",
                "code": "200",
                "gzip_ratio": "-",
                "host": "192.168.16.37",
                "method": "GET",
                "path": "/",
                "referer": "-",
                "size": "2",
                "time": "19/Dec/2023:14:04:39 +0000",
                "user": "-",
            },
        },
        id="parse nginx health check",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "nginx",
                "overwrite_target": True,
            },
        },
        {
            "message": '192.168.42.31 - boat-cmb-write [19/Dec/2024:14:04:33 +0000] "POST /v1/metrics HTTP/1.1" 200 2 "-" "OpenTelemetry Collector for Kubernetes/0.134.0 (linux/amd64)"'
        },
        {
            "message": '192.168.42.31 - boat-cmb-write [19/Dec/2024:14:04:33 +0000] "POST /v1/metrics HTTP/1.1" 200 2 "-" "OpenTelemetry Collector for Kubernetes/0.134.0 (linux/amd64)"',
            "parsed": {
                "agent": "OpenTelemetry Collector for Kubernetes/0.134.0 (linux/amd64)",
                "code": "200",
                "host": "192.168.42.31",
                "method": "POST",
                "path": "/v1/metrics",
                "referer": "-",
                "size": "2",
                "time": "19/Dec/2024:14:04:33 +0000",
                "user": "boat-cmb-write",
            },
        },
        id="parse nginx opentelemetry",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "nginx",
                "overwrite_target": True,
            },
        },
        {
            "message": '192.168.32.9 - - [19/Dec/2023:14:04:32 +0000]  400 "POST /otlp/v1/metrics HTTP/1.1" 462 "-" "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)" "-"'
        },
        {
            "message": '192.168.32.9 - - [19/Dec/2023:14:04:32 +0000]  400 "POST /otlp/v1/metrics HTTP/1.1" 462 "-" "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)" "-"',
            "parsed": {
                "agent": "OpenTelemetry Collector Contrib/0.132.0 (linux/amd64)",
                "code": "400",
                "host": "192.168.32.9",
                "method": "POST",
                "path": "/otlp/v1/metrics",
                "gzip_ratio": "-",
                "referer": "-",
                "size": "462",
                "time": "19/Dec/2023:14:04:32 +0000",
                "user": "-",
            },
        },
        id="parse nginx opentelemetry 2",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc3164",
                "overwrite_target": True,
            },
        },
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        id="parse empty message for syslog rfc 3164 without error",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc3164_local",
                "overwrite_target": True,
            },
        },
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        id="parse empty message for syslog rfc 3164 local without error",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "syslog_rfc5424",
                "overwrite_target": True,
            },
        },
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        {"message": "", "@timestamp": "2026-04-01T10:46:00.682181235Z"},
        id="parse empty message for syslog rfc 5424 without error",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "logfmt",
                "overwrite_target": True,
            },
        },
        {"message": 'level=INFO host=Ubuntu msg="Connected to PostgreSQL database"'},
        {
            "message": 'level=INFO host=Ubuntu msg="Connected to PostgreSQL database"',
            "parsed": {
                "host": "Ubuntu",
                "level": "INFO",
                "msg": "Connected to PostgreSQL database",
            },
        },
        id="parse logfmt",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "logfmt",
                "overwrite_target": True,
            },
        },
        {
            "message": 'time=2012-11-01T22:08:41+00:00 app=loki level=WARN duration=125 message="this is a log line" extra="user=foo"'
        },
        {
            "message": 'time=2012-11-01T22:08:41+00:00 app=loki level=WARN duration=125 message="this is a log line" extra="user=foo"',
            "parsed": {
                "app": "loki",
                "duration": "125",
                "extra": "user=foo",
                "level": "WARN",
                "message": "this is a log line",
                "time": "2012-11-01T22:08:41+00:00",
            },
        },
        id="parse more complex logfmt",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "logfmt",
                "overwrite_target": True,
            },
        },
        {
            "message": "time=2012-11-01T22:08:41+00:00 app.name=loki level=WARN debug="
            ' total_duration=125 message-content="this is a log line"'
            ' extra="user.bonus-info_v2=foo"',
        },
        {
            "message": "time=2012-11-01T22:08:41+00:00 app.name=loki level=WARN debug="
            ' total_duration=125 message-content="this is a log line"'
            ' extra="user.bonus-info_v2=foo"',
            "parsed": {
                "app.name": "loki",
                "total_duration": "125",
                "extra": "user.bonus-info_v2=foo",
                "level": "WARN",
                "message-content": "this is a log line",
                "time": "2012-11-01T22:08:41+00:00",
                "debug": "",
            },
        },
        id="parse logfmt with dots, underscores and hyphens",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "docker",
                "overwrite_target": True,
            },
        },
        {
            "message": '{"log":"log message","stream":"stderr","time":"2019-04-30T02:12:41.8443515Z", "extra": "not expected field"}'
        },
        {
            "message": '{"log":"log message","stream":"stderr","time":"2019-04-30T02:12:41.8443515Z", "extra": "not expected field"}',
            "parsed": {
                "stream": "stderr",
                "output": "log message",
                "timestamp": "2019-04-30T02:12:41.8443515Z",
            },
        },
        id="parse docker with additional fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "message"},
                "source_format": "decolorize",
                "overwrite_target": True,
            },
        },
        {
            "message": "2021-07-14T03:23:44.315Z / \u001b[32minfo\u001b[39m: Server started on port: 3000 - Environment \r\n",
        },
        {
            "message": "2021-07-14T03:23:44.315Z / info: Server started on port: 3000 - Environment \r\n",
        },
        id="decolorize log",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "message"},
                "source_format": "base64",
                "overwrite_target": True,
            },
        },
        {
            "message": "dGhpcyBpcyBlc2NhcGVkIG9uIHdyb25nIHBsYWNlIiBhZnRlciBlc2NhcGUK",
        },
        {
            "message": 'this is escaped on wrong place" after escape\n',
        },
        id="base64 double quote escape",
    ),
)

failure_test_cases = [
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "source_format": "base64",
            },
        },
        {"message": "not base64"},
        {"message": "not base64", "tags": ["_decoder_failure"]},
        id="not base64 source string",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "new_field"},
                "source_format": "base64",
            },
        },
        {"message": "not base64"},
        {"message": "not base64", "tags": ["_decoder_failure"]},
        id="not base64 source string with mapping",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"missing": "new_field"},
                "source_format": "base64",
            },
        },
        {"message": "not base64"},
        {"message": "not base64", "tags": ["_decoder_missing_field_warning"]},
        id="source field not found with mapping",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["missing"],
                "target_field": "new_field",
                "source_format": "base64",
            },
        },
        {"message": "not base64"},
        {"message": "not base64", "tags": ["_decoder_missing_field_warning"]},
        id="source field not found with single source field",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "new_field"},
                "source_format": "json",
            },
        },
        {"message": "not json"},
        {"message": "not json", "tags": ["_decoder_failure"]},
        id="json decode error with mapping",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "source_format": "json",
            },
        },
        {"message": "not json"},
        {"message": "not json", "tags": ["_decoder_failure"]},
        id="json decode error with single field",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "clf",
                "overwrite_target": True,
            },
        },
        {
            "message": '127.0.0.1 ident alice [01/May/2025:07:20:10 +0000] "GET /index.html HTTP/1.1" 200',
        },
        {
            "message": '127.0.0.1 ident alice [01/May/2025:07:20:10 +0000] "GET /index.html HTTP/1.1" 200',
            "tags": ["_decoder_failure"],
        },
        id="parse clf failed",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "nginx",
                "overwrite_target": True,
            },
        },
        {
            "message": "this does not match any nginx pattern",
        },
        {
            "message": "this does not match any nginx pattern",
            "tags": ["_decoder_failure"],
        },
        id="no nginx pattern matches",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "cri",
            },
        },
        {
            "message": "nocri",
        },
        {
            "message": "nocri",
            "tags": ["_decoder_failure"],
        },
        id="not cri",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "docker",
            },
        },
        {
            "message": "notdocker",
        },
        {
            "message": "notdocker",
            "tags": ["_decoder_failure"],
        },
        id="not docker and not json",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "docker",
            },
        },
        {
            "message": '{"message": "this is not the message expected"}',
        },
        {
            "message": '{"message": "this is not the message expected"}',
            "tags": ["_decoder_failure"],
        },
        id="json, but not docker",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "docker",
            },
        },
        {
            "message": '{"log":"log message","time":"2019-04-30T02:12:41.8443515Z"}',
        },
        {
            "message": '{"log":"log message","time":"2019-04-30T02:12:41.8443515Z"}',
            "tags": ["_decoder_failure"],
        },
        id="json, but not docker because one missing",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {"message": "not xml"},
        {"message": "not xml", "tags": ["_decoder_failure"]},
        id="not a windows event log xml",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {"message": "<NotAnEvent/>"},
        {"message": "<NotAnEvent/>", "tags": ["_decoder_failure"]},
        id="windows event log with wrong root element",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {"message": '<Event><EventData><Data Name="x">y</Data></EventData></Event>'},
        {
            "message": '<Event><EventData><Data Name="x">y</Data></EventData></Event>',
            "tags": ["_decoder_failure"],
        },
        id="windows event log without system section",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<EventData><Data>first</Data><Data>second</Data></EventData></Event>"
            )
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<EventData><Data>first</Data><Data>second</Data></EventData></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with unnamed data values",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<EventData><Data><Nested>value</Nested></Data></EventData></Event>"
            )
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<EventData><Data><Nested>value</Nested></Data></EventData></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with nested unnamed data value",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<ProcessingErrorData><ErrorCode>5</ErrorCode></ProcessingErrorData></Event>"
            )
        },
        {
            "message": (
                "<Event><System><EventID>1</EventID></System>"
                "<ProcessingErrorData><ErrorCode>5</ErrorCode></ProcessingErrorData></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with unnamed processing error data",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {"message": """
<!DOCTYPE Event [
    <!ENTITY a "BOOM">
    <!ENTITY b "&a;&a;">
    <!ENTITY c "&b;&b;">
    <!ENTITY d "&c;&c;">
    <!ENTITY e "&d;&d;">
    <!ENTITY f "&e;&e;">
    <!ENTITY g "&f;&f;">
    <!ENTITY h "&g;&g;">
    <!ENTITY i "&h;&h;">
    <!ENTITY j "&i;&i;">
    <!ENTITY k "&j;&j;">
    <!ENTITY l "&k;&k;">
    <!ENTITY m "&l;&l;">
    <!ENTITY n "&m;&m;">
    <!ENTITY o "&n;&n;">
    <!ENTITY p "&o;&o;">
    <!ENTITY q "&p;&p;">
    <!ENTITY r "&q;&q;">
    <!ENTITY s "&r;&r;">
    <!ENTITY t "&s;&s;">
    <!ENTITY u "&t;&t;">
    <!ENTITY v "&u;&u;">
    <!ENTITY w "&v;&v;">
    <!ENTITY x "&w;&w;">
]>
<Event><System><EventID>&x;</EventID></System></Event>
"""},
        {
            "message": """
<!DOCTYPE Event [
    <!ENTITY a "BOOM">
    <!ENTITY b "&a;&a;">
    <!ENTITY c "&b;&b;">
    <!ENTITY d "&c;&c;">
    <!ENTITY e "&d;&d;">
    <!ENTITY f "&e;&e;">
    <!ENTITY g "&f;&f;">
    <!ENTITY h "&g;&g;">
    <!ENTITY i "&h;&h;">
    <!ENTITY j "&i;&i;">
    <!ENTITY k "&j;&j;">
    <!ENTITY l "&k;&k;">
    <!ENTITY m "&l;&l;">
    <!ENTITY n "&m;&m;">
    <!ENTITY o "&n;&n;">
    <!ENTITY p "&o;&o;">
    <!ENTITY q "&p;&p;">
    <!ENTITY r "&q;&q;">
    <!ENTITY s "&r;&r;">
    <!ENTITY t "&s;&s;">
    <!ENTITY u "&t;&t;">
    <!ENTITY v "&u;&u;">
    <!ENTITY w "&v;&v;">
    <!ENTITY x "&w;&w;">
]>
<Event><System><EventID>&x;</EventID></System></Event>
""",
            "tags": ["_decoder_failure"],
        },
        id="windows event log with doctype declaration",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                '<!DOCTYPE Event [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                "<Event><System><EventID>&xxe;</EventID></System></Event>"
            )
        },
        {
            "message": (
                '<!DOCTYPE Event [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                "<Event><System><EventID>&xxe;</EventID></System></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with external entity declaration",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                '<!DOCTYPE Event [<!ENTITY a "abcdefghij"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
                '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
                "<Event><System><EventID>&c;</EventID></System></Event>"
            )
        },
        {
            "message": (
                '<!DOCTYPE Event [<!ENTITY a "abcdefghij"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
                '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
                "<Event><System><EventID>&c;</EventID></System></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with entity expansion",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {"message": "<Event><System><EventID>&undefined;</EventID></System></Event>"},
        {
            "message": "<Event><System><EventID>&undefined;</EventID></System></Event>",
            "tags": ["_decoder_failure"],
        },
        id="windows event log with undefined entity",
    ),
    pytest.param(
        {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
            },
        },
        {
            "message": (
                "<Event><System><Channel>Application</Channel></System><UserData>"
                + "<Data>" * (MAX_XML_DEPTH + 1)
                + "x"
                + "</Data>" * (MAX_XML_DEPTH + 1)
                + "</UserData></Event>"
            )
        },
        {
            "message": (
                "<Event><System><Channel>Application</Channel></System><UserData>"
                + "<Data>" * (MAX_XML_DEPTH + 1)
                + "x"
                + "</Data>" * (MAX_XML_DEPTH + 1)
                + "</UserData></Event>"
            ),
            "tags": ["_decoder_failure"],
        },
        id="windows event log with excessive nesting",
    ),
]

invalid_xmlfield_cases = [
    pytest.param(["EventID"], "must be a dict", id="not a dict"),
    pytest.param(
        {"ID": "EventID"}, "definition of 'ID' must be a dict", id="definition not a dict"
    ),
    pytest.param({"": {"element": "EventID"}}, "non-empty strings", id="empty target"),
    pytest.param({1: {"element": "EventID"}}, "non-empty strings", id="target not a string"),
    pytest.param(
        {"EventID": {"type": "int"}},
        "unknown keys",
        id="unknown key",
    ),
    pytest.param(
        {"Custom": {"convert": "int"}},
        "'element' is required for new target 'Custom'",
        id="no element for new target",
    ),
    pytest.param(
        {"Custom": {"element": ""}},
        "'element' of 'Custom' must be a non-empty string",
        id="empty element",
    ),
    pytest.param(
        {"EventID": {"section": 1}},
        "'section' of 'EventID' must be a string",
        id="section not a string",
    ),
    pytest.param(
        {"EventID": {"section": "RenderingInfo"}},
        "unknown section",
        id="unknown section",
    ),
    pytest.param(
        {"Custom": {"element": "Data", "name": 1}},
        "'name' of 'Custom' must be a string",
        id="name not a string",
    ),
    pytest.param(
        {"EventID": {"attribute": 1}},
        "'attribute' of 'EventID' must be a string",
        id="attribute not a string",
    ),
    pytest.param(
        {"EventID": {"convert": 1}},
        "'convert' of 'EventID' must be a string",
        id="convert not a string",
    ),
    pytest.param(
        {"EventID": {"convert": "float"}},
        "unknown convert type",
        id="unknown convert type",
    ),
]


class TestDecoder(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "decoder",
        "rules": ["tests/testdata/unit/decoder/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        result = self.object.process(event)
        assert event == expected, f"{result.errors}"

    @pytest.mark.parametrize(["rule", "event", "expected"], failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.errors) > 0 or len(result.warnings) > 0
        assert is_list_of(
            result.errors, ProcessingError
        ), f"ProcessingError expected: {result.errors}"
        assert is_list_of(
            result.warnings, ProcessingWarning
        ), f"ProcessingWarning expected: {result.warnings}"
        assert event == expected

    def test_decodes_different_source_json_escaping(self):
        """has to be tested from external file to avoid auto format from black"""
        rule = {
            "filter": "message",
            "decoder": {"source_fields": ["message"], "target_field": "parsed"},
        }
        with open("tests/testdata/unit/decoder/parse.txt", encoding="utf-8") as f:
            for line in f.readlines():
                log_input, source_format, expected_output = line.split(",")
                rule["decoder"]["source_format"] = source_format
                self._load_rule(rule)
                expected_output = expected_output.lstrip().strip("\n")
                event = self.object._decoder.decode(log_input)
                self.object.process(event)
                assert json.dumps(event["parsed"]) == expected_output

    @pytest.mark.parametrize(
        "log_line, expected",
        [
            pytest.param("k=123", {"k": "123"}, id="single character key"),
            pytest.param("=1 \t=2 \n=3 \x1b=4", {}, id="empty key not supported"),
            pytest.param("k=1 =435", {"k": "1"}, id="item before empty key"),
            pytest.param("k=", {"k": ""}, id="empty value"),
            pytest.param("k1= k2=2", {"k1": "", "k2": "2"}, id="item after empty value"),
            pytest.param(
                "key1=value1 key2=value2", {"key1": "value1", "key2": "value2"}, id="multiple keys"
            ),
        ],
    )
    def test_parse_logfmt(self, log_line, expected: dict):
        assert expected == parse_logfmt(log_line)

    @pytest.mark.parametrize("char", [pytest.param(c, id=f"{c} in key name") for c in "*?.|#@/-"])
    def test_parse_logfmt_special_characters(self, char):
        assert {
            f"{char}": "1",
            f"k{char}k": "2",
            f"{char}k": "3",
            f"k{char}": "4",
        } == parse_logfmt(f"{char}=1 k{char}k=2 {char}k=3 k{char}=4")

    @pytest.mark.parametrize(["xmlfields", "expected_message"], invalid_xmlfield_cases)
    def test_invalid_xmlfields(self, xmlfields, expected_message):
        rule = {
            "filter": "message",
            "decoder": {
                "mapping": {"message": "parsed"},
                "source_format": "windows_event_log",
                "xmlfields": xmlfields,
            },
        }
        with pytest.raises(InvalidRuleDefinitionError, match=expected_message):
            self.object.rule_class.create_from_dict(rule)

    def test_xmlfields_only_allowed_with_windows_event_log(self):
        rule = {
            "filter": "message",
            "decoder": {"source_format": "json", "xmlfields": CUSTOM_XMLFIELDS},
        }
        with pytest.raises(InvalidRuleDefinitionError, match="only supported"):
            self.object.rule_class.create_from_dict(rule)

    def test_get_decoder_rejects_xmlfields_for_other_formats(self):
        with pytest.raises(ValueError, match="only supported"):
            get_decoder("json", xmlfields=CUSTOM_XMLFIELDS)
