# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.string_splitter.processor import StringSplitter
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.string_splitter.test_string_splitter import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestStringSplitter(BaseProcessorTestCase[StringSplitter]):
    CONFIG: dict = {
        "type": "ng_string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected"], test_cases)
    async def test_testcases(self, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data["result"] == expected

    @pytest.mark.parametrize(
        ["rule", "event", "expected", "error_message"],
        [
            pytest.param(
                {
                    "filter": "message",
                    "string_splitter": {"source_fields": ["message"], "target_field": "result"},
                },
                {"message": ["this", "is", "the", "message"]},
                {"message": ["this", "is", "the", "message"], "tags": ["_string_splitter_failure"]},
                ".*ProcessingWarning.*",
                id="splits_without_delimiter_on_whitespace_with_no_string",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "string_splitter": {"source_fields": ["message"], "target_field": "message"},
                },
                {"message": "this is the message"},
                {"message": "this is the message", "tags": ["_string_splitter_failure"]},
                ".*FieldExistsWarning.*",
                id="splits_without_delimiter_on_whitespace_with_existing_field",
            ),
        ],
    )
    async def test_testcases_failure_handling(self, rule, event, expected, error_message):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected
