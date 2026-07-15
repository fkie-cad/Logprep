# pylint: disable=missing-docstring
import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.deleter.processor import Deleter
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestDeleter(BaseProcessorTestCase[Deleter]):
    CONFIG = {
        "type": "deleter",
        "rules": ["tests/testdata/unit/deleter/rules"],
    }

    @pytest.mark.parametrize(
        "event, testcase",
        [
            (
                LogEvent(
                    {"not_needed_message": "i am not needed anymore"},
                    original=b"",
                    input_meta=InputMeta(),
                ),
                "deletes simple event",
            ),
            (
                LogEvent(
                    {"not_needed_message": {"nested_block": {"deeper": "string"}}},
                    original=b"",
                    input_meta=InputMeta(),
                ),
                "deletes nested events",
            ),
            (LogEvent({}, original=b"", input_meta=InputMeta()), "deletes empty event"),
        ],
    )
    async def test_process_deletes_event(self, event, testcase):
        await self.object.process(event)
        assert not event.data, testcase
        assert isinstance(event, LogEvent), testcase
        assert isinstance(event.data, dict)
