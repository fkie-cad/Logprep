# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.processor.selective_extractor.filtered_event import FilteredEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestFilteredEvents(TestEventClass):

    def test_sre_event_initialization(self) -> None:
        filtered_event = FilteredEvent(
            data={"foo": "bar"}, output_name="name", output_target="sre_topic"
        )

        assert filtered_event.data == {"foo": "bar"}
        assert filtered_event.output_name == "name"
        assert filtered_event.output_target == "sre_topic"
