# pylint: disable=missing-docstring
# pylint: disable=protected-access

import pytest

from logprep.ng.event_state import EventState, EventStateType


@pytest.mark.parametrize(
    "initial, success, next_expected",
    [
        # Automatic transitions
        (EventStateType.RECEIVING, None, EventStateType.RECEIVED),
        (EventStateType.RECEIVED, None, EventStateType.PROCESSING),
        (EventStateType.PROCESSED, None, EventStateType.STORED_IN_OUTPUT),
        (EventStateType.FAILED, None, EventStateType.STORED_IN_ERROR),
        (EventStateType.DELIVERED, None, EventStateType.ACKED),
        # Ambiguous transitions resolved with success flag
        (EventStateType.STORED_IN_ERROR, True, EventStateType.DELIVERED),
        (EventStateType.STORED_IN_ERROR, False, EventStateType.FAILED),
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
    """Ensure next() correctly advances to the expected state."""

    state = EventState()
    state.current_state = initial
    result = state.next(success=success)
    assert result == next_expected
    assert state.current_state == next_expected


def test_resolve_by_success_flag_returns_correct_result() -> None:
    """Test resolving a next state with success flag (True/False)."""

    assert (
        EventState._resolve_by_success_flag(
            [EventStateType.FAILED, EventStateType.PROCESSED], success=True
        )
        == EventStateType.PROCESSED
    )
    assert (
        EventState._resolve_by_success_flag(
            [EventStateType.FAILED, EventStateType.PROCESSED], success=False
        )
        == EventStateType.FAILED
    )


def test_resolve_by_success_flag_returns_none_if_no_match() -> None:
    """Return None if no state matches success condition."""

    resolve_flag = EventState._resolve_by_success_flag(
        [EventStateType.ACKED],
        success=False,
    )
    assert resolve_flag is None


def test_reset_sets_state_to_initial() -> None:
    """Calling reset() should set the state back to RECEIVING."""
    state = EventState()
    state.current_state = EventStateType.FAILED
    state.reset()
    assert state.current_state == EventStateType.RECEIVING


def test_str_representation() -> None:
    """String representation should be human-readable."""
    state = EventState()
    assert str(state) == "<EventState: receiving>"


def test_next_raises_exception_if_invalid_current_state() -> None:
    """If the current state is not in the state machine, next()
    should raise an ValueError."""

    state = EventState()
    state.current_state = EventStateType.ACKED  # No successors

    with pytest.raises(ValueError, match="Invalid state transition."):
        state.next()


def test_next_raises_exception_when_no_further_state() -> None:
    """If no further transition is defined, next() should return None."""

    state = EventState()
    state.current_state = EventStateType.ACKED

    with pytest.raises(ValueError, match="Invalid state transition."):
        state.next()


def test_next_returns_none_on_ambiguous_without_success() -> None:
    """If multiple options exist but success is not given, next()
    should return None."""

    state = EventState()
    state.current_state = EventStateType.STORED_IN_ERROR

    with pytest.raises(ValueError, match="Invalid state transition."):
        state.next()


def test_all_states_covered_in_state_machine() -> None:
    """Ensure that all EventStateType values are represented
    in the state machine."""

    graph = EventState._construct_state_machine()
    all_keys = set(graph.keys())
    all_targets = {state for targets in graph.values() for state in targets}
    all_used = all_keys.union(all_targets)
    assert set(EventStateType).issubset(all_used)
