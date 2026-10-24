# pylint: disable=missing-docstring
# pylint: disable=line-too-long

from copy import deepcopy

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
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
        "type": "ip_informer",
        "rules": ["tests/testdata/unit/ip_informer/rules/"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    async def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        event = LogEvent(event, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor(config_patch=config) as instance:
            await instance.process(event)

        assert event.data == expected

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], failure_test_cases)
    async def test_testcases_failure_handling(
        self, rule, event, expected, context, provision_context
    ):
        provision_context(context)
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        event = LogEvent(event, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor(config_patch=config) as instance:
            result = await instance.process(event)

        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert event.data == expected
