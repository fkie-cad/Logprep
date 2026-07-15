# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-slots-in-subclass
# pylint: disable=attribute-defined-outside-init


import json

from attrs import define

from logprep.ng.abc.event import ErrorEvent, ExtraDataEvent, InputMeta, LogEvent
from tests.unit.ng.event.test_event import TestEventClass


@define
class DummyChildEvent(ExtraDataEvent):
    pass


class TestErrorEvents(TestEventClass):

    def _create_test_event(self, data):
        return ErrorEvent(data, input_meta=InputMeta())

    def setup_method(self):

        self.child1_event = DummyChildEvent({"c1": 1}, output_name="whatever", output_target=None)
        self.child2_event = DummyChildEvent(
            {"c2": 2}, output_name="whatever", output_target="custom"
        )

        self.log_event = LogEvent(
            data={"foo": "bar"}, original=b"raw", extra_data=[], input_meta=InputMeta()
        )

    def test_event_initializes(self):
        self.log_event.extra_data = [self.child2_event]
        self.log_event.errors.append(ValueError("Some value is wrong"))
        error_event = ErrorEvent.from_failed_event(self.log_event)

        assert isinstance(error_event.data["@timestamp"], str)
        assert error_event.data["original"] == "raw"
        assert isinstance(error_event.data["event"], str)
        assert error_event.data["event"] == '{"foo": "bar"}'
        assert isinstance(error_event.data["reason"], str)
        assert "Some value is wrong" in error_event.data["reason"]
        assert error_event.data["event"] == json.dumps(self.log_event.data)
