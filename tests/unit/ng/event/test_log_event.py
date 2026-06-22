# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import InputMeta, LogEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestLogEvents(TestEventClass):
    def test_log_event_initializes(self):
        log_event = LogEvent(data={"foo": "bar"}, original=b"raw", input_meta=InputMeta())

        assert log_event.original == b"raw"
        assert not log_event.extra_data
