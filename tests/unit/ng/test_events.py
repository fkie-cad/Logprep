# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.ng.event import EventState, EventStateType


@pytest.mark.parametrize(
    "initial, success, next_expected",
    [
        # Automatic transitions (only one possible next state)
        (EventStateType.RECEIVING, None, EventStateType.RECEIVED),
        (EventStateType.RECEIVED, None, EventStateType.PROCESSING),
        (EventStateType.PROCESSED, None, EventStateType.STORED_IN_OUTPUT),
        (EventStateType.FAILED, None, EventStateType.STORED_IN_ERROR),
        (EventStateType.STORED_IN_ERROR, None, EventStateType.FAILED),
        (EventStateType.DELIVERED, None, EventStateType.ACKED),
        # Ambiguous transitions resolved with success flag
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
    """Ensure next() transitions correctly for all defined state cases."""

    state = EventState()
    state.current_state = initial
    result = state.next(success=success)
    assert result == next_expected
    assert state.current_state == next_expected


def test_next_returns_none_on_ambiguous_without_success() -> None:
    """Returns None if multiple options exist but success flag is missing."""

    state = EventState()
    state.current_state = EventStateType.PROCESSING
    result = state.next()
    assert result is None
    assert state.current_state == EventStateType.PROCESSING


def test_next_returns_none_when_no_further_state() -> None:
    """Returns None if already in final state."""

    state = EventState()
    state.current_state = EventStateType.ACKED
    result = state.next()
    assert result is None
    assert state.current_state == EventStateType.ACKED


def test_resolve_by_success_flag_returns_correct_result() -> None:
    """Test success flag resolution in ambiguous transitions."""

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
    """Returns None if no match for success path is found."""

    state = EventState()
    assert state._resolve_by_success_flag([EventStateType.ACKED], success=False) is None


def test_reset_sets_state_to_initial() -> None:
    """Calling reset() sets current state to RECEIVING."""

    state = EventState()
    state.current_state = EventStateType.FAILED
    state.reset()
    assert state.current_state == EventStateType.RECEIVING


def test_str_representation() -> None:
    """__str__ returns readable output."""

    state = EventState()
    assert str(state) == "<EventState: receiving>"
