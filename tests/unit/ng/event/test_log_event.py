# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass
from typing import cast
from unittest.mock import Mock

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState, EventStateType
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestLogEvents(TestEventClass):
    def test_log_event_initializes(self) -> None:
        log_event = LogEvent(data={"foo": "bar"}, original=b"raw")

        assert isinstance(log_event.state, EventState)
        assert log_event.original == b"raw"
        assert not log_event.extra_data
        assert log_event.metadata is None

        assert callable(log_event._origin_state_next_state_fn)
        assert log_event.state.next_state != log_event._origin_state_next_state_fn

    def test_log_event_preserves_state_on_init(self) -> None:
        state = EventState()
        state.current_state = cast(EventStateType, EventStateType.STORED_IN_OUTPUT)
        log_event = LogEvent(data={"msg": "payload"}, original=b"event", state=state)

        assert log_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_log_event_transition_to_delivered_succeeds_if_all_extra_data_delivered(self) -> None:
        child1 = DummyEvent({"c1": 1})
        child2 = DummyEvent({"c2": 2})
        child1.state.current_state = cast(EventStateType, EventStateType.DELIVERED)
        child2.state.current_state = cast(EventStateType, EventStateType.DELIVERED)

        log_event = LogEvent(
            data={"parent": "yes"},
            original=b"...",
            extra_data=[child1, child2],
        )
        log_event.state.current_state = cast(EventStateType, EventStateType.STORED_IN_OUTPUT)

        log_event.state.next_state(success=True)
        assert log_event.state.current_state is EventStateType.DELIVERED

    def test_log_event_transition_to_next_state_excluding_delivered(self) -> None:

        log_event = LogEvent(
            data={"parent": "yes"},
            original=b"...",
            extra_data=[],
        )
        log_event.state.current_state = cast(EventStateType, EventStateType.PROCESSING)

        log_event.state.next_state(success=True)
        assert log_event.state.current_state is EventStateType.PROCESSED

    def test_log_event_transition_to_delivered_fails_if_extra_data_not_delivered(self) -> None:
        child1 = DummyEvent({"c1": 1})
        child2 = DummyEvent({"c2": 2})
        child1.state.current_state = cast(EventStateType, EventStateType.DELIVERED)
        child2.state.current_state = cast(EventStateType, EventStateType.FAILED)

        log_event = LogEvent(data={"parent": "e"}, original=b"...", extra_data=[child1, child2])
        log_event.state.current_state = cast(EventStateType, EventStateType.STORED_IN_OUTPUT)

        with pytest.raises(ValueError, match="not all extra_data events are DELIVERED"):
            log_event.state.next_state(success=True)

    def test_next_state_validation_helper_returns_new_state(self):
        sub_event = Mock(spec=Event)
        sub_event.state.current_state = EventStateType.DELIVERED

        log_event = LogEvent(
            data={"msg": "parent"},
            original=b"raw",
            extra_data=[sub_event],
        )

        log_event._origin_state_next_state_fn = Mock(return_value=EventStateType.DELIVERED)

        result = log_event._next_state_validation_helper(success=True)

        assert result is EventStateType.DELIVERED
