# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-statements
# pylint: disable=too-many-lines
# pylint: disable=import-error

from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.key_checker.processor import KeyChecker
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.key_checker.test_key_checker import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestKeyChecker(BaseProcessorTestCase[KeyChecker]):
    CONFIG = {
        "type": "ng_key_checker",
        "rules": ["tests/testdata/unit/key_checker/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    async def test_testcases_positive(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data == expected, testcase

    async def test_field_exists_warning(self):
        rule_dict = {
            "filter": "*",
            "key_checker": {
                "source_fields": ["not.existing.key"],
                "target_field": "missing_fields",
            },
        }
        await self._load_rule(rule_dict)
        document = {
            "key1": {
                "key2": {"key3": {"key3": "key3_value"}, "random_key": "random_key_value"},
                "_index": "value",
            },
            "randomkey2": "randomvalue2",
            "missing_fields": ["i.exists.already"],
        }
        event = LogEvent(document, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
