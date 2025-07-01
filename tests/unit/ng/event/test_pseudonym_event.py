# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState, EventStateType
from logprep.ng.event.pseudonym_event import PseudonymEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestPseudonymEvents(TestEventClass):

    def test_pseudonym_event_initializes(self) -> None:
        pseudonym_event = PseudonymEvent(data={"foo": "bar"})

        assert isinstance(pseudonym_event.state, EventState)

    def test_pseudonym_event_preserves_state_on_init(self) -> None:
        state = EventState()
        state.current_state = EventStateType.STORED_IN_OUTPUT
        pseudonym_event = PseudonymEvent(data={"msg": "payload"}, state=state)

        assert pseudonym_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_pseudonym_event_transition_to_next(self) -> None:

        pseudonym_event = PseudonymEvent(
            data={"parent": "yes"},
        )
        pseudonym_event.state.current_state = EventStateType.PROCESSING

        pseudonym_event.state.next_state(success=True)
        assert pseudonym_event.state.current_state == EventStateType.PROCESSED
