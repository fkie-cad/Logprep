# pylint: disable=missing-docstring
# pylint: disable=protected-access

import pytest

from logprep.ng.event import EventState, EventStateType


@pytest.mark.parametrize(
    "initial, success, next_expected",
    [
        # Automatic transitions
        (EventStateType.RECEIVING, None, EventStateType.RECEIVED),
        (EventStateType.RECEIVED, None, EventStateType.PROCESSING),
        (EventStateType.PROCESSED, None, EventStateType.STORED_IN_OUTPUT),
        (EventStateType.FAILED, None, EventStateType.STORED_IN_ERROR),
        (EventStateType.DELIVERED, None, EventStateType.ACKED),
        # Now ambiguous transition for STORED_IN_ERROR
        (EventStateType.STORED_IN_ERROR, True, EventStateType.DELIVERED),
        (EventStateType.STORED_IN_ERROR, False, EventStateType.FAILED),
        # Other ambiguous transitions
        (EventStateType.PROCESSING, True, EventStateType.PROCESSED),
        (EventStateType.PROCESSING, False, EventStateType.FAILED),
        (EventStateType.STORED_IN_OUTPUT, True, EventStateType.DELIVERED),
        (EventStateType.STORED_IN_OUTPUT, False, EventStateType.FAILED),
    ],
)
def test_next_transitions_correctly(
    initial: EventStateType,
    success: bool | None,
    next_expected: EventStateType,
) -> None:
    state = EventState()
    state.current_state = initial
    result = state.next(success=success)
    assert result == next_expected
    assert state.current_state == next_expected


def test_next_returns_none_on_ambiguous_without_success() -> None:
    state = EventState()
    state.current_state = EventStateType.STORED_IN_ERROR
    result = state.next()
    assert result is None
    assert state.current_state == EventStateType.STORED_IN_ERROR


def test_next_returns_none_when_no_further_state() -> None:
    state = EventState()
    state.current_state = EventStateType.ACKED
    result = state.next()
    assert result is None
    assert state.current_state == EventStateType.ACKED


def test_resolve_by_success_flag_returns_correct_result() -> None:
    state = EventState()
    assert (
        state._resolve_by_success_flag(
            [EventStateType.FAILED, EventStateType.PROCESSED], success=True
        )
        == EventStateType.PROCESSED
    )
    assert (
        state._resolve_by_success_flag(
            [EventStateType.FAILED, EventStateType.PROCESSED], success=False
        )
        == EventStateType.FAILED
    )


def test_resolve_by_success_flag_returns_none_if_no_match() -> None:
    state = EventState()
    assert state._resolve_by_success_flag([EventStateType.ACKED], success=False) is None


def test_reset_sets_state_to_initial() -> None:
    state = EventState()
    state.current_state = EventStateType.FAILED
    state.reset()
    assert state.current_state == EventStateType.RECEIVING


def test_str_representation() -> None:
    state = EventState()
    assert str(state) == "<EventState: receiving>"
