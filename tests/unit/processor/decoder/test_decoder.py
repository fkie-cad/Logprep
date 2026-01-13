# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
import json

import pytest

from tests.unit.processor.base import BaseProcessorTestCase


class TestDecoder(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "decoder",
        "rules": ["tests/testdata/unit/decoder/rules"],
    }

    @pytest.mark.parametrize(
        "rule, event, expected",
        [
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
                id="decodes_simple_json_to_target_field",
            ),
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
                id="decodes_json_with_mapping_to_corresponding_target_fields",
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
                id="decodes_simple_base64",
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
                id="decodes_simple_base64_and_removes_source_field",
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
                id="decodes_simple_base64_and_removes_source_fields_with_mapping",
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
                id="decodes_simple_base64_and_overwrites_source_fields",
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
                {
                    "message": "<34>Oct 3 10:15:32 su[12345]: 'su root' failed for user on /dev/pts/0"
                },
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
        ],
    )
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        result = self.object.process(event)
        assert event == expected, f"{result.errors}"

    @pytest.mark.parametrize(
        "rule, event, expected",
        [
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
                id="not_base64_source_string",
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
                id="not_base64_source_string_with_mapping",
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
                id="source_field_not_found_with_mapping",
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
                id="source_field_not_found_with_single_source_field",
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
                id="json_decode_error_with_mapping",
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
                id="json_decode_error_with_single_field",
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
                id="not cri ",
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
        ],
    )
    def test_testcases_failure_handling(self, rule, event, expected):
        self._load_rule(rule)
        result = self.object.process(event)
        assert result.errors or result.warnings
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
