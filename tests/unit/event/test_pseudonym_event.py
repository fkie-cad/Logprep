# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.abc.event import Event
from logprep.event.event_state import EventState, EventStateType
from logprep.event.pseudonym_event import PseudonymEvent
from tests.unit.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestPseudonymEvents(TestEventClass):

    def test_pseudonym_event_initializes(self) -> None:
        outputs = ({"opensearch": "pseudonym_index"},)
        pseudonym_event = PseudonymEvent(data={"foo": "bar"}, outputs=outputs)

        assert isinstance(pseudonym_event.state, EventState)
        assert pseudonym_event.state.current_state is EventStateType.PROCESSED

    def test_pseudonym_event_preserves_state_on_init(self) -> None:
        state = EventStateType.STORED_IN_OUTPUT
        outputs = ({"opensearch": "pseudonym_index"},)
        pseudonym_event = PseudonymEvent(data={"msg": "payload"}, state=state, outputs=outputs)

        assert pseudonym_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_pseudonym_event_transition_to_next(self) -> None:
        outputs = ({"opensearch": "pseudonym_index"},)
        pseudonym_event = PseudonymEvent(data={"parent": "yes"}, outputs=outputs)
        pseudonym_event.state.current_state = EventStateType.PROCESSING

        pseudonym_event.state.next_state(success=True)
        assert pseudonym_event.state.current_state == EventStateType.PROCESSED
