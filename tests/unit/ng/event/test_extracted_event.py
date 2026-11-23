# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.processor.selective_extractor.extracted_event import ExtractedEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestExtractedEvents(TestEventClass):

    def _create_test_event(self, data):
        return ExtractedEvent(data, output_name="test1", output_target="test2")

    def test_event_initializes(self) -> None:
        extracted_event = ExtractedEvent(
            data={"foo": "bar"}, output_name="name", output_target="sre_topic"
        )

        assert extracted_event.data == {"foo": "bar"}
        assert extracted_event.output_name == "name"
        assert extracted_event.output_target == "sre_topic"
