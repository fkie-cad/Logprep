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
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestStringSplitter(BaseProcessorTestCase[StringSplitter]):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    async def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        event = LogEvent(event, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor(config_patch=config) as instance:
            await instance.process(event)

        assert event.data["result"] == expected
