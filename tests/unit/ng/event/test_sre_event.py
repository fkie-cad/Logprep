# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState, EventStateType
from logprep.ng.event.sre_event import SreEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestSreEvents(TestEventClass):

    def test_sre_event_initialisation(self) -> None:
        outputs = ({"name": "sre_topic"},)
        data = {"foo": "bar"}
        sre_event = SreEvent(data=data, outputs=outputs)

        assert sre_event.data == data
        assert sre_event.outputs == outputs
        assert isinstance(sre_event.state, EventState)

    def test_sre_event_preserves_state_on_init(self) -> None:
        state = EventState()
        state.current_state = EventStateType.STORED_IN_OUTPUT
        outputs = ({"name": "sre_topic"},)
        sre_event = SreEvent(data={"msg": "payload"}, state=state, outputs=outputs)

        assert sre_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_sre_event_transition_to_next(self) -> None:
        outputs = ({"name": "sre_topic"},)
        sre_event = SreEvent(data={"parent": "yes"}, outputs=outputs)
        sre_event.state.current_state = EventStateType.PROCESSING

        sre_event.state.next_state(success=True)
        assert sre_event.state.current_state == EventStateType.PROCESSED
