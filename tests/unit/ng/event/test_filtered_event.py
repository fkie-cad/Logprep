# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event
from logprep.ng.event.event_state import EventState, EventStateType
from logprep.ng.event.filtered_event import FilteredEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestFilteredEvents(TestEventClass):

    def test_sre_event_initialisation(self) -> None:
        outputs = ({"name": "sre_topic"},)
        data = {"foo": "bar"}
        filtered_event = FilteredEvent(data=data, outputs=outputs)

        assert filtered_event.data == data
        assert filtered_event.outputs == outputs
        assert isinstance(filtered_event.state, EventState)

    def test_sre_event_preserves_state_on_init(self) -> None:
        state = EventState()
        state.current_state = EventStateType.STORED_IN_OUTPUT
        outputs = ({"name": "sre_topic"},)
        sre_event = FilteredEvent(data={"msg": "payload"}, state=state, outputs=outputs)

        assert sre_event.state.current_state is EventStateType.STORED_IN_OUTPUT

    def test_sre_event_transition_to_next(self) -> None:
        outputs = ({"name": "sre_topic"},)
        sre_event = FilteredEvent(data={"parent": "yes"}, outputs=outputs)
        sre_event.state.current_state = EventStateType.PROCESSING

        sre_event.state.next_state(success=True)
        assert sre_event.state.current_state == EventStateType.PROCESSED
