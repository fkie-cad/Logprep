# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.string_splitter.processor import StringSplitter
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.string_splitter.test_string_splitter import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.string_splitter.test_string_splitter import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestStringSplitter(BaseProcessorTestCase[StringSplitter]):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    async def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        await self._load_rule(rule)
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        assert event.data["result"] == expected

    @pytest.mark.parametrize(["rule", "event", "expected", "error_message"], failure_test_cases)
    async def test_testcases_failure_handling(self, rule, event, expected, error_message):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event.data == expected
