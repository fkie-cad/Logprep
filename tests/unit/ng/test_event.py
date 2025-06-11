import pickle
from typing import Any

import pytest

from logprep.ng.abc.event import Event
from logprep.ng.event_state import EventState


class DummyEvent(Event):
    """
    Concrete subclass of Event used for testing, with enforced __slots__.
    """

    __slots__ = Event.__slots__


def test_event_initialization_defaults() -> None:
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


def test_event_initialization_with_custom_state() -> None:
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


def test_event_data_as_positional_argument() -> None:
    """
    Ensure that the Event can be instantiated using a positional argument for 'data'.
    """

    event = DummyEvent({"source": "positional"})

    assert event.data["source"] == "positional"
    assert isinstance(event.state, EventState)


def test_event_data_as_keyword_argument() -> None:
    """
    Ensure that the Event can also be instantiated using 'data' as a keyword argument.
    """

    event = DummyEvent(data={"source": "keyword"})

    assert event.data["source"] == "keyword"
    assert isinstance(event.state, EventState)


def test_event_valid_state_positional_argument() -> None:
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
