# pylint: disable=missing-docstring

import pytest

from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog


class TestSetEventBacklog:
    def test_register_adds_events(self):
        backlog = SetEventBacklog()

        e1 = LogEvent(data={"foo": "bar"}, original=b"")
        e2 = LogEvent(data={"john": "doe"}, original=b"")

        backlog.register([e1, e2])

        assert len(backlog.backlog) == 2
        assert e1 in backlog.backlog
        assert e2 in backlog.backlog

    def test_get_returns_events_but_does_not_remove(self):
        backlog = SetEventBacklog()

        e1 = LogEvent(data={"foo": "bar"}, original=b"")
        e1.state.current_state = EventStateType.RECEIVED

        e2 = LogEvent(data={"john": "doe"}, original=b"")
        e3 = LogEvent(data={"state": "done"}, original=b"")

        backlog.register([e1, e2, e3])
        result = backlog.get(EventStateType.RECEIVED)

        assert len(result) == 1
        assert len(backlog.backlog) == 3

    def test_unregister_removes_events_with_failed_state(self):
        backlog = SetEventBacklog()

        e1 = LogEvent(data={"foo": "bar"}, original=b"")
        e1.state.current_state = EventStateType.ACKED

        e2 = LogEvent(data={"john": "doe"}, original=b"")
        e2.state.current_state = EventStateType.FAILED

        e3 = LogEvent(data={"state": "done"}, original=b"")

        backlog.register([e1, e2, e3])
        result = backlog.unregister(EventStateType.FAILED)

        assert e2 in result
        assert e1 in backlog.backlog
        assert e2 not in backlog.backlog
        assert e3 in backlog.backlog

    def test_unregister_removes_events_with_acked_state(self):
        backlog = SetEventBacklog()

        e1 = LogEvent(data={"foo": "bar"}, original=b"")
        e1.state.current_state = EventStateType.ACKED

        e2 = LogEvent(data={"john": "doe"}, original=b"")
        e2.state.current_state = EventStateType.FAILED

        e3 = LogEvent(data={"state": "done"}, original=b"")
        e3.state.current_state = EventStateType.ACKED

        backlog.register([e1, e2, e3])
        result = backlog.unregister(state_type=EventStateType.ACKED)

        assert e1 in result
        assert e3 in result
        assert e1 not in backlog.backlog
        assert e2 in backlog.backlog
        assert e3 not in backlog.backlog

    def test_unregister_with_invalid_state_raises(self):
        backlog = SetEventBacklog()

        with pytest.raises(ValueError, match="Invalid state_type"):
            backlog.unregister(state_type=EventStateType.STORED_IN_ERROR)  # type: ignore
