# pylint: disable=missing-docstring

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
        "decodes escaped json to target field",
        {
            "filter": "message",
            "decoder": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        #fmt: off
        {"message": "{\"to_decode\": \"decode value\"}"},
        #fmt: on
        {"message": '{"to_decode": "decode value"}', "new_field": {"to_decode": "decode value"}},
    ),
      (  "decodes json and escaped json with mapping to corresponding target fields",
        {
            "filter": "json_message OR escaped_message",
            "decoder": {
                "mapping": {
                    "json_message": "json_field",
                    "escaped_message": "escaped_field"
                }
            },
        },
        #fmt: off
        {"escaped_message": "{\"to_decode\": \"decode value\"}", 
            "json_message": '{"json_decode": "json_value"}'
        },
        {"escaped_message": "{\"to_decode\": \"decode value\"}", 
            "json_message": '{"json_decode": "json_value"}',
            "json_field": {"json_decode": "json_value"},
            "escaped_field": {"to_decode": "decode value"},
        },
        #fmt: on
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
