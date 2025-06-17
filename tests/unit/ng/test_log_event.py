# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState, EventStateType
from logprep.ng.events.log_event import LogEvent


class DummyEvent(Event):
    __slots__ = Event.__slots__


def test_log_event_initializes_correctly() -> None:
    log_event = LogEvent(data={"foo": "bar"}, original=b"raw")

    assert isinstance(log_event.state, EventState)
    assert log_event.original == b"raw"
    assert not log_event.extra_data
    assert log_event.metadata is None
    assert callable(log_event._origin_state_next_state_fn)
    assert log_event.state.next_state is not log_event._origin_state_next_state_fn


def test_log_event_preserves_state_on_init() -> None:
    state = EventState()
    state.current_state = EventStateType.STORED_IN_OUTPUT
    log_event = LogEvent(data={"msg": "payload"}, original=b"event", state=state)

    assert log_event.state.current_state is EventStateType.STORED_IN_OUTPUT


def test_log_event_transition_to_delivered_fails_if_extra_data_not_delivered() -> None:
    child = DummyEvent({"foo": 1})
    child.state.current_state = EventStateType.PROCESSED
    log_event = LogEvent(data={"parent": "e"}, original=b"...", extra_data=[child])
    log_event.state.current_state = EventStateType.STORED_IN_OUTPUT

    with pytest.raises(ValueError, match="not all extra_data events are DELIVERED"):
        log_event.state.next_state(success=True)


def test_log_event_direct_state_assignment_succeeds_if_all_extra_data_delivered() -> None:
    child = DummyEvent({"child": "ok"})
    child.state.current_state = EventStateType.DELIVERED
    log_event = LogEvent(data={"parent": "x"}, original=b"...", extra_data=[child])
    new_state = EventState()
    new_state.current_state = EventStateType.DELIVERED
    log_event.state = new_state

    assert log_event.state.current_state is EventStateType.DELIVERED
