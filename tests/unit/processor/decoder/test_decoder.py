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
        ],
    )
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

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
