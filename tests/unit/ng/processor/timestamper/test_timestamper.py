# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.ng.processor.timestamper.processor import Timestamper
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.timestamper.test_timestamper import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.timestamper.test_timestamper import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestTimestamper(BaseProcessorTestCase[Timestamper]):
    CONFIG: dict = {
        "type": "ng_timestamper",
        "rules": ["tests/testdata/unit/timestamper/rules"],
    }

    async def test_is_field_manager_implementation(self):
        assert isinstance(self.object, FieldManager)
        assert issubclass(self.object.rule_class, FieldManager.rule_class)

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    async def test_testcases(self, testcase, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    async def test_testcases_failure_handling(self, testcase, rule, event, expected, error_message):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
        assert event.data == expected, testcase
