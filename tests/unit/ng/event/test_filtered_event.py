# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event, OutputSpec
from logprep.ng.event.filtered_event import FilteredEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestFilteredEvents(TestEventClass):

    def test_sre_event_initialization(self) -> None:
        outputs = (OutputSpec("name", "sre_topic"),)
        data = {"foo": "bar"}
        filtered_event = FilteredEvent(data=data, outputs=outputs)

        assert filtered_event.data == data
        assert filtered_event.outputs == outputs
