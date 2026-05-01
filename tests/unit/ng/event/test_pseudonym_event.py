# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass


from logprep.ng.abc.event import OutputSpec
from logprep.ng.event.pseudonym_event import PseudonymEvent
from tests.unit.ng.event.test_event import TestEventClass


class TestPseudonymEvents(TestEventClass):

    def test_pseudonym_event_initializes(self) -> None:
        outputs = (OutputSpec("opensearch", "pseudonym_index"),)
        data = {"foo": "bar"}
        pseudonym_event = PseudonymEvent(data=data, outputs=outputs)

        assert pseudonym_event.data == data
        assert pseudonym_event.outputs == outputs
