# pylint: disable=missing-docstring

from typing import Sequence

import pytest

from logprep.ng.abc.event import Event, EventBacklog
from logprep.ng.event.event_state import EventStateType


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestEventBacklog:
    def test_missing_register_raises(self):
        class MissingRegister(EventBacklog):
            def unregister(self, state_type: EventStateType) -> Sequence[Event]:
                return []

            def get(self, state_type: EventStateType) -> Sequence[Event]:
                return []

        backlog = MissingRegister()

        with pytest.raises(NotImplementedError):
            backlog.register([])

    def test_missing_unregister_raises(self):
        class MissingUnregister(EventBacklog):
            def register(self, events: Sequence[Event]) -> None:
                pass

            def get(self, state_type: EventStateType) -> Sequence[Event]:
                return []

        backlog = MissingUnregister()

        with pytest.raises(NotImplementedError):
            backlog.unregister(EventStateType.ACKED)

    def test_missing_get_raises(self):
        class MissingGet(EventBacklog):
            def register(self, events: Sequence[Event]) -> None:
                pass

            def unregister(self, state_type: EventStateType) -> Sequence[Event]:
                return []

        backlog = MissingGet()

        with pytest.raises(NotImplementedError):
            backlog.get(EventStateType.RECEIVED)

    def test_unregister_with_invalid_state_raises(self):
        class DummyBacklog(EventBacklog):
            def register(self, events: Sequence[Event]) -> None:
                pass

            def unregister(self, state_type: EventStateType) -> Sequence[Event]:
                return []

            def get(self, state_type: EventStateType) -> Sequence[Event]:
                return []

        backlog = DummyBacklog()

        with pytest.raises(ValueError, match="Invalid state_type"):
            backlog.unregister("unexpected")  # type: ignore

    def test_unregister_with_valid_state_calls_original_method(self):
        called_states = []

        class DummyBacklog(EventBacklog):
            def register(self, events: Sequence[Event]) -> None:
                pass

            def unregister(self, state_type: EventStateType) -> Sequence[Event]:
                called_states.append(state_type)
                return [DummyEvent({"id": 1})]

            def get(self, state_type: EventStateType) -> Sequence[Event]:
                return []

        backlog = DummyBacklog()
        result = backlog.unregister(EventStateType.FAILED)

        assert isinstance(result[0], DummyEvent)
        assert called_states == [EventStateType.FAILED]
