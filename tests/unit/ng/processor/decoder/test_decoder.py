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
from tests.unit.processor.decoder.test_decoder import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.decoder.test_decoder import test_cases as non_ng_test_cases

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


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
        failure_test_cases,
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
