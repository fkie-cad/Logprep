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
from logprep.ng.abc.processor import Processor
from logprep.ng.processor.string_splitter.processor import StringSplitter
from tests.conftest import ProcessorFailureTestCase, ProcessorTestCase
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.string_splitter.test_string_splitter import (
    parametrized_failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.string_splitter.test_string_splitter import (
    parametrized_test_cases as non_ng_test_cases,
)

parametrized_test_cases = deepcopy(non_ng_test_cases)
parametrized_failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestStringSplitter(BaseProcessorTestCase[StringSplitter]):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize("case", parametrized_test_cases)
    async def test_testcases(self, case: ProcessorTestCase, provision_context_new):
        if case.context is not None:
            provision_context_new(case.context)
        await self._load_rule(case.rule)
        event = LogEvent(case.event, original=b"", input_meta=InputMeta())
        assert isinstance(self.object, Processor)
        await self.object.process(event)
        assert event.data["result"] == case.expected

    @pytest.mark.parametrize("case", parametrized_failure_test_cases)
    async def test_testcases_failure_handling(
        self, case: ProcessorFailureTestCase, provision_context_new
    ):
        if case.context is not None:
            provision_context_new(case.context)
        await self._load_rule(case.rule)
        event = LogEvent(case.event, original=b"", input_meta=InputMeta())
        assert isinstance(self.object, Processor)
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(case.error_message, str(result.warnings[0]))
        assert event.data == case.expected
