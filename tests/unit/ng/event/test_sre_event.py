# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import Event, OutputSpec
from logprep.ng.event.sre_event import SreEvent
from tests.unit.ng.event.test_event import TestEventClass


class DummyEvent(Event):
    __slots__ = Event.__slots__


class TestSreEvents(TestEventClass):

    def test_sre_event_initialization(self) -> None:
        outputs = (OutputSpec("name", "sre_topic"),)
        data = {"foo": "bar"}
        sre_event = SreEvent(data=data, outputs=outputs)

        assert sre_event.data == data
        assert sre_event.outputs == outputs
