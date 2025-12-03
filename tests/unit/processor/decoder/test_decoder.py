# pylint: disable=missing-docstring
# pylint: disable=protected-access

import json

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "decodes simple json to target field",
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {"message": '{"to_decode": "decode value"}'},
        {"message": '{"to_decode": "decode value"}', "new_field": {"to_decode": "decode value"}},
    ),
    (
        "decodes json with mapping to corresponding target fields",
        {
            "filter": "json_message OR escaped_message",
            "decoder": {
                "mapping": {"json_message": "json_field", "escaped_message": "escaped_field"}
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
    ),
    (
        "decodes simple base64",
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
    ),
]

failure_test_cases = []  # testcase, rule, event, expected


class TestDecoder(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "decoder",
        "rules": ["tests/testdata/unit/decoder/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase

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
