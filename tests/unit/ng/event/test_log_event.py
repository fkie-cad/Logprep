# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestLogEvents(TestEventClass):
    def test_log_event_initializes(self):
        log_event = LogEvent(data={"foo": "bar"}, original=b"raw")

        assert log_event.original == b"raw"
        assert not log_event.extra_data
        assert log_event.metadata is None
