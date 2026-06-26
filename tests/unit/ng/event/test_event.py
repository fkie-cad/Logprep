# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=too-few-public-methods
# pylint: disable=protected-access
# pylint: disable=unnecessary-dunder-call


import pickle
from abc import ABC, abstractmethod

import pytest

from logprep.ng.abc.event import OutputEvent
from logprep.util.helper import FieldValue


class TestEventClass(ABC):

    @abstractmethod
    def _create_test_event(self, data: dict[str, FieldValue]) -> OutputEvent:
        """
        Template method for creating a basic event instance
        """

    def test_event_equality_for_equal_data(self):

        event1 = self._create_test_event({"user": {"id": 42, "name": "Alice"}})
        event2 = self._create_test_event({"user": {"id": 42, "name": "Alice"}})

        assert event1 == event2

    def test_event_inequality_for_different_data(self):

        event1 = self._create_test_event({"user": {"id": 41, "name": "Alice"}})
        event2 = self._create_test_event({"user": {"id": 42, "name": "Alice"}})

        assert event1 != event2

    def test_event_eq_not_implemented(self):

        event = self._create_test_event(data={"key": "value"})
        non_event = {"key": "value"}

        assert (event == non_event) is False
        assert event.__eq__(non_event) is NotImplemented

    @pytest.mark.parametrize(
        ("data", "error"),
        [
            ({"message": "A test message"}, None),
            ({"user": "alice"}, None),
            ({"id": 123}, ValueError("invalid id")),
            (
                {"foo": "bar"},
                RuntimeError("processing error"),
            ),
            (
                {"status": "ok"},
                None,
            ),
            (
                {"service": "auth"},
                TimeoutError("Service did not respond"),
            ),
        ],
    )
    def test_event_is_picklable(self, data: dict[str, FieldValue], error: Exception | None):
        """
        Ensure that DummyEvent instances with type-consistent
        data, warnings (strings), and errors (Exception instances)
        can be pickled and unpickled correctly - with and without custom EventState.
        """

        event = self._create_test_event(data=data)

        if error:
            event.mark_failed(error)

        dumped = pickle.dumps(event)
        loaded = pickle.loads(dumped)

        assert isinstance(loaded, event.__class__)
        assert isinstance(loaded.data, dict)

        assert loaded.data == data
