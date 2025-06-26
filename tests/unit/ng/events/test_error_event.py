# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=attribute-defined-outside-init


import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState, EventStateType
from logprep.ng.events.error_event import ErrorEvent
from logprep.ng.events.log_event import LogEvent
from tests.unit.ng.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestErrorEvents(TestEventClass):

    def setup_method(self):

        self.child1_event = DummyEvent({"c1": 1})
        self.child2_event = DummyEvent({"c2": 2})
        self.child1_event.state.current_state = EventStateType.DELIVERED
        self.child2_event.state.current_state = EventStateType.FAILED

        self.log_event = LogEvent(
            data={"foo": "bar"},
            original=b"raw",
            extra_data=[],
        )

    def test_error_event_initializes_correctly(self) -> None:
        self.log_event.extra_data = [self.child2_event]
        error_event = ErrorEvent(log_event=self.log_event)

        assert isinstance(error_event.data["@timestamp"], str)
        assert error_event.data["original"] == b"raw"
        assert isinstance(error_event.data["event"], bytes)
        assert error_event.data["event"] == b'{"foo":"bar"}'

    def test_error_event_preserves_state_on_init(self) -> None:
        state = EventState()
        state.current_state = EventStateType.STORED_IN_OUTPUT

        self.log_event.state.current_state = EventStateType.FAILED
        error_event = ErrorEvent(log_event=self.log_event, state=state)

        assert error_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_error_event_with_no_failed_extra_data_sets_reason_for_log_event(self):
        self.log_event.extra_data = [self.child1_event]
        self.log_event.state.current_state = EventStateType.FAILED
        error_event = ErrorEvent(log_event=self.log_event)

        assert error_event.data["reason"] == "log event couldn't be processed or delivered"
        assert isinstance(error_event.data["@timestamp"], str)
        assert error_event.data["original"] == b"raw"
        assert isinstance(error_event.data["event"], bytes)

    def test_error_event_with_failed_extra_data_sets_reason_for_log_event(self):
        self.log_event.extra_data = [self.child1_event, self.child2_event]
        error_event = ErrorEvent(log_event=self.log_event)

        assert error_event.data["reason"] == "extra data event couldn't be delivered"

    def test_error_event_with_no_failed_events_raises_error(self):
        with pytest.raises(ValueError, match="No failed events detected"):
            ErrorEvent(log_event=self.log_event)

    def test_unserializable_event_raises_encode_error(self):
        self.log_event.extra_data = [self.child2_event]
        self.log_event.data["bad"] = lambda x: x + 1
        with pytest.raises(TypeError):
            ErrorEvent(log_event=self.log_event)
