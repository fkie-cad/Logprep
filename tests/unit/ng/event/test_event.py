# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=too-few-public-methods
# pylint: disable=protected-access
# pylint: disable=unnecessary-dunder-call

import pickle
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from logprep.ng.abc.event import Event


class DummyEvent(Event):
    __slots__ = Event.__slots__


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

    def test_event_eq_not_implemented(self):

        event = Event(data={"key": "value"})
        non_event = {"key": "value"}

        assert (event == non_event) is False
        assert event.__eq__(non_event) is NotImplemented

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

    def test_event_deep_freeze_on_set(self):
        """
        Ensure that _deep_freeze transforms nested dicts/lists into hashable
        frozen structures.
        """
        e = DummyEvent({})
        input_set = {1, 2, 3}
        frozen = e._deep_freeze(input_set)

        assert isinstance(frozen, frozenset)
        assert frozen == frozenset({1, 2, 3})

    def test_event_initialization_defaults(self):
        """
        Verify that the Event initializes correctly when no custom state
        is provided.

        It should:
        - Store the provided data payload
        - Initialize empty error list
        """

        payload = {"message": "A test message"}
        event = DummyEvent(payload)

        assert event.data == payload
        assert event.errors == []

    def test_event_data_as_positional_argument(self):
        """
        Ensure that the Event can be instantiated using a positional
        argument for 'data'.
        """

        event = DummyEvent({"source": "positional"})

        assert event.data["source"] == "positional"

    def test_event_data_as_keyword_argument(self):
        """
        Ensure that the Event can also be instantiated using 'data' as
        a keyword argument.
        """

        event = DummyEvent(data={"source": "keyword"})

        assert event.data["source"] == "keyword"

    @pytest.mark.parametrize(
        "data, warnings, errors",
        [
            ({"message": "A test message"}, [], []),
            ({"user": "alice"}, [Warning("Low confidence")], []),
            ({"id": 123}, [], [ValueError("invalid id")]),
            (
                {"foo": "bar"},
                [DeprecationWarning("Deprecated format")],
                [RuntimeError("processing error")],
            ),
            (
                {"status": "ok"},
                [],
                [],
            ),
            (
                {"service": "auth"},
                [RuntimeWarning("auth timeout")],
                [TimeoutError("Service did not respond")],
            ),
        ],
    )
    def test_event_is_picklable_with_values(
        self, data: dict[str, Any], warnings: list[Exception], errors: list[Exception]
    ):
        """
        Ensure that DummyEvent instances with type-consistent
        data, warnings (strings), and errors (Exception instances)
        can be pickled and unpickled correctly – with and without custom EventState.
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

        assert loaded.data == data
        assert loaded.warnings == warnings
        assert [str(e) for e in loaded.errors] == [str(e) for e in errors]

    def test_add_fields_to_delegates_correctly(self):
        dummy = DummyEvent({"user": {"id": 42}})
        fields = {"key": "value"}
        rule = MagicMock()

        with patch("logprep.ng.abc.event.add_fields_to") as mock_add:
            dummy.add_fields_to(fields, rule, merge_with_target=True, overwrite_target=True)
            mock_add.assert_called_once()

    def test_get_dotted_field_delegates_correctly(self):
        dummy = DummyEvent({"user": {"id": 42}})
        field = "id"

        with patch("logprep.ng.abc.event.get_dotted_field_value") as mock_get:
            dummy.get_dotted_field_value(field)
            mock_get.assert_called_once()

    def test_pop_dotted_field_delegates_correctly(self):
        dummy = DummyEvent({"user": {"id": 42}})
        field = "user"

        with patch("logprep.ng.abc.event.pop_dotted_field_value") as mock_pop:
            dummy.pop_dotted_field_value(field)
            mock_pop.assert_called_once()

    def test_event_repr(self):
        event = DummyEvent({"user": {"id": 42, "name": "Alice"}})
        assert repr(event) == "DummyEvent(data={'user': {'id': 42, 'name': 'Alice'}})"
