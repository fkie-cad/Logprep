# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=attribute-defined-outside-init


import json

from logprep.ng.abc.event import Event
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestErrorEvents(TestEventClass):

    def setup_method(self):

        self.child1_event = DummyEvent({"c1": 1})
        self.child2_event = DummyEvent({"c2": 2})

        self.log_event = LogEvent(
            data={"foo": "bar"},
            original=b"raw",
            extra_data=[],
        )

    def test_error_event_initializes(self):
        self.log_event.extra_data = [self.child2_event]
        self.log_event.errors.append(ValueError("Some value is wrong"))
        error_event = ErrorEvent.from_failed_event(self.log_event)

        assert isinstance(error_event.data["@timestamp"], str)
        assert error_event.data["original"] == "raw"
        assert isinstance(error_event.data["event"], str)
        assert error_event.data["event"] == '{"foo": "bar"}'
        assert isinstance(error_event.data["reason"], str)
        assert "Some value is wrong" in error_event.data["reason"]
        assert error_event.data["event"] == json.dumps(self.log_event.data)
