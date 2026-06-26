# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.processor.pseudonymizer.pseudonym_event import PseudonymEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestPseudonymEvents(TestEventClass):

    def _create_test_event(self, data):
        return PseudonymEvent(data, output_name="test1", output_target="test2")

    def test_event_initializes(self):
        pseudonym_event = PseudonymEvent(
            data={"foo": "bar"}, output_name="opensearch", output_target="pseudonym_index"
        )

        assert pseudonym_event.data == {"foo": "bar"}
        assert pseudonym_event.output_name == "opensearch"
        assert pseudonym_event.output_target == "pseudonym_index"
