# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.processor.pre_detector.sre_event import SreEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestSreEvents(TestEventClass):

    def test_sre_event_initialization(self) -> None:
        sre_event = SreEvent(data={"foo": "bar"}, output_name="name", output_target="sre_topic")

        assert sre_event.data == {"foo": "bar"}
        assert sre_event.output_name == "name"
        assert sre_event.output_target == "sre_topic"
