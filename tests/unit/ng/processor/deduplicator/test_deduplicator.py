# pylint: disable=missing-docstring
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

from copy import deepcopy

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.deduplicator.test_deduplicator import (
    test_cases as non_ng_testcases,
)

test_cases = deepcopy(non_ng_testcases)


class TestDeduplicator(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "deduplicator",
        "rules": ["tests/testdata/unit/deduplicator/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    async def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        await self._load_rule(rule)
        log_event = LogEvent(event, original=b"test_message", input_meta=InputMeta())
        await self.object.process(log_event)
        assert log_event.data == expected
