# pylint: disable=missing-docstring
# pylint: disable=protected-access

import pytest

from logprep.ng.event.event_state import EventState, EventStateType


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
):
    """Ensure next_state() correctly advances to the expected state."""

    state = EventState()
    state.current_state = initial
    result = state.next_state(success=success)
    assert result == next_expected
    assert state.current_state == next_expected


def test_resolve_by_success_flag_returns_correct_result():
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


def test_resolve_by_success_flag_returns_none_if_no_match():
    """Return None if no state matches success condition."""

    resolve_flag = EventState._resolve_by_success_flag(
        [EventStateType.ACKED],
        success=False,
    )
    assert resolve_flag is None


def test_reset_sets_state_to_initial():
    """Calling reset() should set the state back to RECEIVING."""
    state = EventState()
    state.current_state = EventStateType.FAILED
    state.reset()
    assert state.current_state == EventStateType.RECEIVING


def test_str_representation():
    """String representation should be human-readable."""
    state = EventState()
    assert str(state) == "receiving"


def test_next_raises_exception_when_no_further_state():
    """If no further transition is defined, next_state() should return None."""

    state = EventState()
    state.current_state = EventStateType.ACKED

    with pytest.raises(
        ValueError, match="Invalid state transition: Already reached terminal state"
    ):
        state.next_state()


@pytest.mark.parametrize(
    "current_state, success, expected",
    [
        # STORED_IN_OUTPUT -> ...
        (
            EventStateType.STORED_IN_OUTPUT,
            None,
            pytest.raises(ValueError, match="Ambiguous event without success"),
        ),
        (EventStateType.STORED_IN_OUTPUT, True, EventStateType.DELIVERED),
        (EventStateType.STORED_IN_OUTPUT, False, EventStateType.FAILED),
        # STORED_IN_ERROR -> ...
        (
            EventStateType.STORED_IN_ERROR,
            None,
            pytest.raises(ValueError, match="Ambiguous event without success"),
        ),
        (EventStateType.STORED_IN_ERROR, True, EventStateType.DELIVERED),
        (EventStateType.STORED_IN_ERROR, False, EventStateType.FAILED),
    ],
)
def test_next_state_handles_ambiguous_transitions_with_or_without_success_flag(
    current_state, success, expected
):
    """
    Handle ambiguous transitions based on the success flag.
    Raises ValueError if success is not provided.
    """

    state = EventState()
    state.current_state = current_state

    if isinstance(expected, type(pytest.raises(ValueError))):
        with expected:
            state.next_state(success=success)
    else:
        result = state.next_state(success=success)
        assert result == expected
        assert state.current_state == expected


def test_all_states_covered_in_state_machine():
    """Ensure that all EventStateType values are represented
    in the state machine."""

    graph = EventState._construct_state_machine()
    all_keys = set(graph.keys())
    all_targets = {state for targets in graph.values() for state in targets}
    all_used = all_keys.union(all_targets)
    assert set(EventStateType).issubset(all_used)


@pytest.mark.parametrize(
    "state1, state2, expected",
    [
        (EventStateType.RECEIVING, EventStateType.RECEIVING, True),
        (EventStateType.RECEIVING, EventStateType.RECEIVED, False),
        (EventState(), EventState(), True),
        (EventState(), EventStateType.RECEIVING, True),
        (EventState(), EventStateType.DELIVERED, False),
        (EventState(), object(), False),
        (EventStateType.DELIVERED, "delivered", False),
    ],
)
def test_equality(state1, state2, expected):
    """Test equality of EventState instances."""
    state_a = EventState() if isinstance(state1, EventStateType) else state1
    state_b = EventState() if isinstance(state2, EventStateType) else state2
    if isinstance(state1, EventStateType):
        state_a.current_state = state1
    if isinstance(state2, EventStateType):
        state_b.current_state = state2
    assert (state_a == state_b) is expected
    assert (state_a != state_b) is not expected
