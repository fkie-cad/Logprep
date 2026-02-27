# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
import json
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import ProcessingError, ProcessingWarning
from logprep.util.typing import is_list_of
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.decoder.test_decoder import test_cases as non_ng_test_cases

test_cases = deepcopy(non_ng_test_cases)


class TestDecoder(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "ng_decoder",
        "rules": ["tests/testdata/unit/decoder/rules"],
    }

    @pytest.mark.parametrize(
        "rule, event, expected",
        test_cases,
    )
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = self.object.process(event)
        assert event.data == expected, f"{result.errors}"

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
        event = LogEvent(event, original=b"")
        result = self.object.process(event)
        assert len(result.errors) > 0 or len(result.warnings) > 0
        assert is_list_of(
            result.errors, ProcessingError
        ), f"ProcessingError expected: {result.errors}"
        assert is_list_of(
            result.warnings, ProcessingWarning
        ), f"ProcessingWarning expected: {result.warnings}"
        assert event.data == expected

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
                event = LogEvent(event, original=b"")
                self.object.process(event)
                assert json.dumps(event.data["parsed"]) == expected_output
