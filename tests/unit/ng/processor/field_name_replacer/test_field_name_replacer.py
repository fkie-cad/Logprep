# pylint: disable=missing-docstring
from copy import deepcopy

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.field_name_replacer.processor import FieldNameReplacer
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.field_name_replacer.test_field_name_replacer import (
    DEFAULT_RULE,
)
from tests.unit.processor.field_name_replacer.test_field_name_replacer import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestFieldNameReplacer(BaseProcessorTestCase[FieldNameReplacer]):
    CONFIG = {
        "type": "field_name_replacer",
        "rules": [DEFAULT_RULE],
    }

    @pytest.mark.parametrize("rule, event, expected, _context", test_cases)
    async def test_replaces_characters_in_field_names(self, rule, event, expected, _context):
        await self._load_rule(rule)

        result = await self.object.process(LogEvent(event, original=b"", input_meta=InputMeta()))

        assert not result.errors
        assert result.data == expected
