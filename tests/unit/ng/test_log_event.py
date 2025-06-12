# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState, EventStateType
from logprep.ng.events.log_event import LogEvent, LogEventState


class DummyEvent(Event):
    __slots__ = Event.__slots__


class DummyMetadata:
    pass


def test_log_event_initializes_with_log_event_state() -> None:
    """
    Ensure that LogEvent automatically wraps state in a LogEventState instance.
    """

    log_event = LogEvent(
        data={"foo": "bar"},
        original=b"raw-bytes",
    )

    assert isinstance(log_event.state, LogEventState)
    assert log_event.original == b"raw-bytes"
    assert not log_event.extra_data
    assert log_event.metadata is None


def test_log_event_preserves_state_on_init() -> None:
    """
    Ensure LogEvent preserves the state from passed EventState
    but wraps it into LogEventState.
    """

    state = EventState()
    state.current_state = EventStateType.STORED_IN_OUTPUT

    log_event = LogEvent(
        data={"msg": "payload"},
        original=b"event-bytes",
        state=state,
    )

    assert isinstance(log_event.state, LogEventState)
    assert log_event.state.current_state is EventStateType.STORED_IN_OUTPUT


def test_log_event_transition_to_delivered_fails_if_extra_data_not_delivered() -> None:
    """
    Prevent state transition to DELIVERED if any extra_data event is not DELIVERED.
    """

    child1 = DummyEvent({"foo": 1})
    child1.state.current_state = EventStateType.PROCESSED  # not delivered

    log_event = LogEvent(
        data={"parent": "event"},
        original=b"...",
        extra_data=[child1],
    )

    log_event.state.current_state = EventStateType.STORED_IN_OUTPUT

    with pytest.raises(ValueError, match="not all extra_data events are DELIVERED."):
        log_event.state.next(success=True)


def test_log_event_transition_to_delivered_succeeds_if_all_extra_data_delivered() -> None:
    """
    Allow transition to DELIVERED if all extra_data events are in DELIVERED.
    """

    child1 = DummyEvent({"foo": 1})
    child1.state.current_state = EventStateType.DELIVERED
    child2 = DummyEvent({"bar": 2})
    child2.state.current_state = EventStateType.DELIVERED

    log_event = LogEvent(
        data={"parent": "event"},
        original=b"...",
        extra_data=[child1, child2],
    )

    log_event.state.current_state = EventStateType.STORED_IN_OUTPUT
    result = log_event.state.next(success=True)

    assert result is EventStateType.DELIVERED
    assert log_event.state.current_state is EventStateType.DELIVERED


def test_log_event_direct_state_assignment_fails_if_extra_data_not_delivered() -> None:
    """
    Ensure direct assignment of EventState with DELIVERED fails
    if extra_data is not fully delivered.
    """

    child = DummyEvent({"child": "e"})
    child.state.current_state = EventStateType.PROCESSING

    log_event = LogEvent(
        data={"parent": "x"},
        original=b"...",
        extra_data=[child],
    )

    new_state = EventState()
    new_state.current_state = EventStateType.DELIVERED

    with pytest.raises(ValueError, match="not all extra_data events are DELIVERED"):
        log_event.state = new_state


def test_log_event_direct_state_assignment_succeeds_if_extra_data_delivered() -> None:
    """
    Allow direct assignment of EventState with DELIVERED if all extra_data events are DELIVERED.
    """

    child = DummyEvent({"child": "ok"})
    child.state.current_state = EventStateType.DELIVERED

    log_event = LogEvent(
        data={"parent": "x"},
        original=b"...",
        extra_data=[child],
    )

    new_state = EventState()
    new_state.current_state = EventStateType.DELIVERED

    log_event.state = new_state
    assert log_event.state.current_state is EventStateType.DELIVERED
