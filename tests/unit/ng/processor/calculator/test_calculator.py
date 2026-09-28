# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-locals

from copy import deepcopy

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.calculator.processor import Calculator
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.calculator.test_calculator import (
    runtime_failure_test_cases as non_ng_runtime_failure_testcases,
)
from tests.unit.processor.calculator.test_calculator import (
    setup_failure_test_cases as non_ng_setup_failure_testcases,
)
from tests.unit.processor.calculator.test_calculator import (
    test_cases as non_ng_testcases,
)

test_cases = deepcopy(non_ng_testcases)
runtime_failure_test_cases = deepcopy(non_ng_runtime_failure_testcases)
setup_failure_test_cases = deepcopy(non_ng_setup_failure_testcases)


class TestCalculator(BaseProcessorTestCase[Calculator]):
    CONFIG: dict = {
        "type": "calculator",
        "rules": ["tests/testdata/unit/calculator/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    async def test_testcases(self, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        assert event.data == expected

    @pytest.mark.parametrize("rule, event, expected", runtime_failure_test_cases)
    async def test_testcases_failure_handling_at_runtime(self, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert event.data == expected

    @pytest.mark.parametrize("rule, error_type", setup_failure_test_cases)
    async def test_testcases_failure_handling_at_setup(self, rule, error_type):
        with pytest.raises(error_type):
            await self._load_rule(rule)
