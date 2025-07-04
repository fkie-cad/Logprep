# pylint: disable=missing-docstring
import pytest

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestDeleter(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_deleter",
        "rules": ["tests/testdata/unit/deleter/rules"],
    }

    @pytest.mark.parametrize(
        "event, testcase",
        [
            (
                LogEvent({"not_needed_message": "i am not needed anymore"}, original=b""),
                "deletes simple event",
            ),
            (
                LogEvent(
                    {"not_needed_message": {"nested_block": {"deeper": "string"}}}, original=b""
                ),
                "deletes nested events",
            ),
            (LogEvent({}, original=b""), "deletes empty event"),
        ],
    )
    def test_process_deletes_event(self, event, testcase):
        self.object.process(event)
        assert not event.data, testcase
        assert isinstance(event, LogEvent), testcase
        assert isinstance(event.data, dict)
