# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=too-few-public-methods

import pickle
from typing import Any

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState
from logprep.processor.base.exceptions import FieldExistsWarning


class DummyEvent(Event):
    __slots__ = Event.__slots__


class DummyRule:
    def __init__(self):
        self.id = "dummy_rule"
        self.description = "Dummy rule description"
        self.source_fields = []
        self.metrics = type("metrics", (), {"number_of_warnings": 0})()


class TestEventClassStructure:
    def test_event_initialization_defaults(self) -> None:
        """
        Verify that the Event initializes correctly when no custom state is provided.

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
        Ensure that the Event can be instantiated using a positional argument for 'data'.
        """

        event = DummyEvent({"source": "positional"})

        assert event.data["source"] == "positional"
        assert isinstance(event.state, EventState)

    def test_event_data_as_keyword_argument(self) -> None:
        """
        Ensure that the Event can also be instantiated using 'data' as a keyword argument.
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
        "data, warnings, errors",
        [
            ({"message": "A test message"}, [], []),
            ({"user": "alice"}, ["Low confidence"], []),
            ({"id": 123}, [], [ValueError("invalid id")]),
            ({"foo": "bar"}, ["Deprecated format"], [RuntimeError("processing error")]),
        ],
    )
    def test_event_is_picklable_with_typed_values(
        self,
        data: dict[str, Any],
        warnings: list[str],
        errors: list[Exception],
    ) -> None:
        """
        Ensure that DummyEvent instances with type-consistent
        data, warnings (strings), and errors (Exception instances)
        can be pickled and unpickled correctly.
        """

        event = DummyEvent(data=data)
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
