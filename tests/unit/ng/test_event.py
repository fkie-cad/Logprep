# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=too-few-public-methods
# pylint: disable=protected-access

import pickle
from typing import Any

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState, EventStateType
from logprep.processor.base.exceptions import FieldExistsWarning


class DummyEvent(Event):
    __slots__ = Event.__slots__


class DummyRule:
    def __init__(self):
        self.id = "dummy_rule"
        self.description = "Dummy rule description"
        self.source_fields = []
        self.metrics = type("metrics", (), {"number_of_warnings": 0})()


class TestEventState:
    # pylint: disable=missing-docstring
    # pylint: disable=protected-access

    @pytest.mark.parametrize(
        "current_state, success, next_expected",
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
        self,
        current_state: EventStateType,
        success: bool | None,
        next_expected: EventStateType,
    ) -> None:
        """Ensure next() correctly advances to the expected state."""

        state = EventState()
        state.current_state = current_state
        result = state.next_state(success=success)
        assert result == next_expected
        assert state.current_state == next_expected

    def test_next_returns_none_on_ambiguous_without_success(self) -> None:
        """If multiple options exist but success is not given, next()
        should return None."""

        state = EventState()
        state.current_state = EventStateType.STORED_IN_ERROR
        result = state.next_state()
        assert result is None
        assert state.current_state == EventStateType.STORED_IN_ERROR

    def test_next_returns_none_when_no_further_state(self) -> None:
        """If no further transition is defined, next() should return None."""

        state = EventState()
        state.current_state = EventStateType.ACKED
        result = state.next_state()
        assert result is None
        assert state.current_state == EventStateType.ACKED

    def test_resolve_by_success_flag_returns_correct_result(self) -> None:
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

    def test_resolve_by_success_flag_returns_none_if_no_match(self) -> None:
        """Return None if no state matches success condition."""

        resolve_flag = EventState._resolve_by_success_flag(
            [EventStateType.ACKED],
            success=False,
        )
        assert resolve_flag is None

    def test_reset_sets_state_to_initial(self) -> None:
        """Calling reset() should set the state back to RECEIVING."""
        state = EventState()
        state.current_state = EventStateType.FAILED
        state.reset()
        assert state.current_state == EventStateType.RECEIVING

    def test_str_representation(self) -> None:
        """String representation should be human-readable."""
        state = EventState()
        assert str(state) == "<EventState: receiving>"

    def test_next_returns_none_if_invalid_current_state(self) -> None:
        """If the current state is not in the state machine, next()
        should return None."""

        state = EventState()
        state.current_state = EventStateType.ACKED  # No successors
        assert state.next_state() is None

    def test_all_states_covered_in_state_machine(self) -> None:
        """Ensure that all EventStateType values are represented
        in the state machine."""

        graph = EventState._construct_state_machine()
        all_keys = set(graph.keys())
        all_targets = {state for targets in graph.values() for state in targets}
        all_used = all_keys.union(all_targets)
        assert set(EventStateType).issubset(all_used)


class TestEventClass:
    def test_event_equality_and_hashing_with_identical_data(self):
        """
        Ensure that two Events with identical data are considered equal
        and have identical hashes.
        """

        event1 = DummyEvent({"user": {"id": 42, "name": "Alice"}})
        event2 = DummyEvent({"user": {"id": 42, "name": "Alice"}})

        assert event1 == event2
        assert hash(event1) == hash(event2)

    def test_event_inequality_with_different_data(self):
        """
        Ensure that Events with different data are not equal and produce
        different hashes.
        """

        event1 = DummyEvent({"user": {"id": 42}})
        event2 = DummyEvent({"user": {"id": 99}})

        assert event1 != event2
        assert hash(event1) != hash(event2)

    def test_event_usable_as_dict_key_and_set_element(self):
        """
        Ensure that Event instances can be used as dictionary keys or
        stored in sets. Equality is based on the contents of self.data.
        """

        e1 = DummyEvent({"id": 1})
        e2 = DummyEvent({"id": 1})
        e3 = DummyEvent({"id": 2})

        event_dict = {e1: "exists"}
        assert event_dict[e2] == "exists"

        event_set = {e1, e3}
        assert e2 in event_set
        assert len(event_set) == 2

    def test_event_set_membership_reduces_duplicates_by_data_equality(self):
        """
        Ensure that adding multiple Event instances with identical `data`
        results in a set of length 1.
        """

        event1 = DummyEvent({"x": [1, 2, 3], "y": {"z": "abc"}})
        event2 = DummyEvent({"x": [1, 2, 3], "y": {"z": "abc"}})

        event_set = {event1, event2}

        assert len(event_set) == 1
        assert event1 in event_set
        assert event2 in event_set

    def test_event_deep_freeze_on_nested_structure(self):
        """
        Ensure that _deep_freeze transforms nested dicts/lists into hashable
        frozen structures.
        """
        e = DummyEvent({})
        nested = {"a": [1, {"b": 2}], "c": {"d": [3, 4]}}

        frozen = e._deep_freeze(nested)

        assert isinstance(frozen, frozenset)
        assert ("a", (1, frozenset({("b", 2)}))) in frozen
        assert ("c", frozenset({("d", (3, 4))})) in frozen

    def test_event_initialization_defaults(self) -> None:
        """
        Verify that the Event initializes correctly when no custom state
        is provided.

        It should:
        - Create a default EventState instance
        - Store the provided data payload
        - Initialize empty error and warning lists
        """

        payload = {"message": "A test message"}
        event = DummyEvent(payload)

        assert isinstance(event.state, EventState)
        assert event.data == payload
        assert event.errors == []
        assert event.warnings == []

    def test_event_initialization_with_custom_state(self) -> None:
        """
        Verify that a custom EventState is properly assigned to the Event.

        The provided state instance should be used directly,
        and the other attributes must still initialize correctly.
        """

        state = EventState()
        payload = {"message": "A test message"}

        event = DummyEvent(data=payload, state=state)

        assert event.state is state
        assert event.data == payload
        assert isinstance(event.errors, list)
        assert isinstance(event.warnings, list)
        assert event.errors == []
        assert event.warnings == []

    def test_event_data_as_positional_argument(self) -> None:
        """
        Ensure that the Event can be instantiated using a positional
        argument for 'data'.
        """

        event = DummyEvent({"source": "positional"})

        assert event.data["source"] == "positional"
        assert isinstance(event.state, EventState)

    def test_event_data_as_keyword_argument(self) -> None:
        """
        Ensure that the Event can also be instantiated using 'data' as
        a keyword argument.
        """

        event = DummyEvent(data={"source": "keyword"})

        assert event.data["source"] == "keyword"
        assert isinstance(event.state, EventState)

    def test_event_valid_state_positional_argument(self) -> None:
        """
        Ensure that providing 'state' as a kw argument is allowed.
        """

        DummyEvent({"source": "fail"}, state=EventState())

    @pytest.mark.parametrize(
        "data, warnings, errors, state",
        [
            ({"message": "A test message"}, [], [], None),
            ({"user": "alice"}, ["Low confidence"], [], None),
            ({"id": 123}, [], [ValueError("invalid id")], None),
            (
                {"foo": "bar"},
                ["Deprecated format"],
                [RuntimeError("processing error")],
                None,
            ),
            (
                {"status": "ok"},
                [],
                [],
                EventState(),
            ),
            (
                {"service": "auth"},
                ["auth timeout"],
                [TimeoutError("Service did not respond")],
                EventState(),
            ),
        ],
    )
    def test_event_is_picklable_with_values(
        self,
        data: dict[str, Any],
        warnings: list[str],
        errors: list[Exception],
        state: EventState | None,
    ) -> None:
        """
        Ensure that DummyEvent instances with type-consistent
        data, warnings (strings), and errors (Exception instances)
        can be pickled and unpickled correctly – with and without custom EventState.
        """

        event = DummyEvent(data=data, state=state)
        event.warnings = warnings
        event.errors = errors

        dumped = pickle.dumps(event)
        loaded = pickle.loads(dumped)

        assert isinstance(loaded, DummyEvent)
        assert isinstance(loaded.data, dict)
        assert all(isinstance(w, str) for w in loaded.warnings)
        assert all(isinstance(e, Exception) for e in loaded.errors)
        assert isinstance(loaded.state, EventState)

        assert loaded.data == data
        assert loaded.warnings == warnings
        assert [str(e) for e in loaded.errors] == [str(e) for e in errors]


class TestGetDottedFieldValue:
    def test_get_dotted_field_value_nesting_depth_zero(self):
        e = DummyEvent({"dotted": "127.0.0.1"})
        assert e.get_dotted_field_value("dotted") == "127.0.0.1"

    def test_get_dotted_field_value_nesting_depth_one(self):
        e = DummyEvent({"dotted": {"field": "127.0.0.1"}})
        assert e.get_dotted_field_value("dotted.field") == "127.0.0.1"

    def test_get_dotted_field_value_nesting_depth_two(self):
        e = DummyEvent({"some": {"dotted": {"field": "127.0.0.1"}}})
        assert e.get_dotted_field_value("some.dotted.field") == "127.0.0.1"

    def test_get_dotted_field_retrieves_sub_dict(self):
        e = DummyEvent({"some": {"dotted": {"field": "127.0.0.1"}}})
        assert e.get_dotted_field_value("some.dotted") == {"field": "127.0.0.1"}

    def test_get_dotted_field_retrieves_list(self):
        e = DummyEvent({"some": {"dotted": ["list", "with", "values"]}})
        assert e.get_dotted_field_value("some.dotted") == ["list", "with", "values"]

    def test_get_dotted_field_value_that_does_not_exist(self):
        e = DummyEvent({})
        assert e.get_dotted_field_value("field") is None

    def test_get_dotted_field_value_that_does_not_exist_from_nested_dict(self):
        e = DummyEvent({"some": {}})
        assert e.get_dotted_field_value("some.dotted.field") is None

    def test_get_dotted_field_value_that_matches_part_of_dotted_field(self):
        e = DummyEvent({"some": "do_not_match"})
        assert e.get_dotted_field_value("some.dotted") is None

    def test_get_dotted_field_value_key_matches_value(self):
        e = DummyEvent({"get": "dotted"})
        assert e.get_dotted_field_value("get.dotted") is None

    def test_get_dotted_field_with_list(self):
        e = DummyEvent({"get": ["dotted"]})
        assert e.get_dotted_field_value("get.0") == "dotted"

    def test_get_dotted_field_with_nested_list(self):
        e = DummyEvent({"get": ["dotted", ["does_not_matter", "target"]]})
        assert e.get_dotted_field_value("get.1.1") == "target"

    def test_get_dotted_field_with_list_not_found(self):
        e = DummyEvent({"get": ["dotted"]})
        assert e.get_dotted_field_value("get.0.1") is None

    def test_get_dotted_field_with_list_last_element(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.-1") == "target"

    def test_get_dotted_field_with_out_of_bounds_index(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.3") is None

    def test_get_dotted_fields_with_list_slicing(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.0:2") == ["dotted", "does_not_matter"]

    def test_get_dotted_fields_with_list_slicing_short(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.:2") == ["dotted", "does_not_matter"]

    def test_get_dotted_fields_reverse_order_with_slicing(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.::-1") == ["target", "does_not_matter", "dotted"]

    def test_get_dotted_fiels_with_list_slicing_2(self):
        e = DummyEvent({"get": ["dotted", "does_not_matter", "target"]})
        assert e.get_dotted_field_value("get.::2") == ["dotted", "target"]


class TestPopDottedFieldValue:
    def test_get_dotted_field_removes_source_field_in_nested_structure_but_leaves_sibling(self):
        e = DummyEvent({"get": {"nested": "field", "other": "field"}})
        value = e.pop_dotted_field_value("get.nested")

        assert value == "field"
        assert e.data == {"get": {"other": "field"}}

    def test_get_dotted_field_removes_source_field(self):
        e = DummyEvent({"get": {"nested": "field"}})
        value = e.pop_dotted_field_value("get.nested")

        assert value == "field"
        assert not e.data

    def test_get_dotted_field_removes_source_field2(self):
        e = DummyEvent({"get": {"very": {"deeply": {"nested": {"field": "value"}}}}})
        value = e.pop_dotted_field_value("get.very.deeply.nested")

        assert value == {"field": "value"}
        assert not e.data


class TestEventAddFields:
    def test_add_field_single_success(self):
        e = DummyEvent({})
        e.add_fields_to({"a.b": 1}, rule=DummyRule())

        assert e.data == {"a": {"b": 1}}

    def test_add_field_merge_dict_success(self):
        e = DummyEvent({"a": {"b": {"x": 1}}})
        e.add_fields_to(
            {"a.b": {"y": 2}},
            rule=DummyRule(),
            merge_with_target=True,
        )

        assert e.data == {"a": {"b": {"x": 1, "y": 2}}}

    def test_add_field_merge_list_success(self):
        e = DummyEvent({"a": {"b": [1]}})
        e.add_fields_to({"a.b": [2]}, rule=DummyRule(), merge_with_target=True)

        assert e.data == {"a": {"b": [1, 2]}}

    def test_add_field_merge_scalar_into_list(self):
        e = DummyEvent({"a": {"b": [1]}})
        e.add_fields_to({"a.b": 2}, rule=DummyRule(), merge_with_target=True)

        assert e.data == {"a": {"b": [1, 2]}}

    def test_add_field_merge_list_into_scalar(self):
        e = DummyEvent({"a": {"b": 1}})
        e.add_fields_to({"a.b": [2]}, rule=DummyRule(), merge_with_target=True)

        assert e.data == {"a": {"b": [1, 2]}}

    def test_add_field_merge_dict_fail_without_flag(self):
        e = DummyEvent({"a": {"b": {"x": 1}}})
        rule = DummyRule()

        with pytest.raises(FieldExistsWarning) as excinfo:
            e.add_fields_to({"a.b": {"y": 2}}, rule=rule)

        assert excinfo.value.skipped_fields == ["a.b"]
        assert rule.metrics.number_of_warnings == 1

    def test_add_field_overwrite(self):
        e = DummyEvent({"a": {"b": 1}})
        e.add_fields_to(
            {"a.b": {"x": 2}},
            rule=DummyRule(),
            overwrite_target=True,
        )

        assert e.data == {"a": {"b": {"x": 2}}}

    def test_add_multiple_fields_with_one_conflict(self):
        e = DummyEvent({"a": {"b": 1}, "c": {}})
        rule = DummyRule()

        with pytest.raises(FieldExistsWarning) as excinfo:
            e.add_fields_to(
                {"a.b": 9, "c.d": 5},
                rule=rule,
            )

        assert excinfo.value.skipped_fields == ["a.b"]
        assert e.data["c"]["d"] == 5

        # _add_field_to_silent_fail internally calls _add_field_to and
        # catches FieldExistsWarning. For each individual failure,
        # rule.metrics.number_of_warnings is incremented – hence the value is 2.
        assert rule.metrics.number_of_warnings == 2

    def test_add_fields_skips_none_values(self):
        e = DummyEvent({})
        e.add_fields_to({"a.b": None, "x.y": 1}, rule=DummyRule())

        assert "a" not in e.data
        assert e.data["x"]["y"] == 1
