# pylint: disable=missing-docstring
# pylint: disable=line-too-long

from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.ip_informer.processor import IpInformer
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.ip_informer.test_ip_informer import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.ip_informer.test_ip_informer import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestIpInformer(BaseProcessorTestCase[IpInformer]):
    CONFIG: dict = {
        "type": "ng_ip_informer",
        "rules": ["tests/testdata/unit/ip_informer/rules/"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    async def test_testcases(self, testcase, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data == expected, testcase

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    async def test_testcases_failure_handling(self, testcase, rule, event, expected):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert event.data == expected, testcase
