# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from copy import deepcopy

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.sre_event import SreEvent
from tests.unit.ng.connector.base import BaseOutputTestCase


class TestDummyOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "ng_dummy_output",
    }

    def test_store_appends_document_to_variable(self):
        document = {"the": "document"}
        event = LogEvent(document, original=b"")
        self.object.store(event)

        assert len(self.object.events) == 1
        assert self.object.events[0].data == document

    def test_store_custom_appends_document_to_variable(self):
        document = {"the": "document"}
        event = LogEvent(document, original=b"")
        self.object.store_custom(event, target="whatever")

        assert len(self.object.events) == 1
        assert self.object.events[0].data == document

    def test_increments_shutdown_called_count_when_shutdown_was_called(self):
        assert self.object.shut_down_called_count == 0
        self.object.shut_down()
        assert self.object.shut_down_called_count == 1

    def test_store_maintains_order_of_documents(self):
        for i in range(0, 3):
            event = LogEvent({"order": i}, original=b"")
            self.object.store(event)
        assert len(self.object.events) == 3
        for order in range(0, 3):
            event = self.object.events[order]
            assert event.data["order"] == order

    def test_raises_exception_on_call_to_store(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})

        event = LogEvent({"order": 0}, original=b"")
        dummy_output.store(event)
        assert len(event.errors) == 1

    def test_raises_exception_on_call_to_store_custom(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event = SreEvent(
            {"order": 0},
            state="processed",
            outputs=({"test_instance_name": "stdout"},),
        )
        dummy_output.store_custom(event, target="whatever")
        assert len(event.errors) == 1

    def test_raises_exception_only_once(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event = LogEvent({"order": 0}, original=b"")
        dummy_output.store(event)
        dummy_output.store(event)
        assert len(event.errors) == 1, "Expected only one error, but got multiple."

    def test_raises_exception_only_when_not_none(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": [None, "FatalOutputError", None]})
        dummy_output = Factory.create({"test connector": config})
        event = LogEvent({"order": 0}, original=b"")
        dummy_output.store(event)
        assert len(event.errors) == 0, "Expected no error, but got one."
        event = LogEvent({"order": 2}, original=b"")
        dummy_output.store(event)
        assert len(event.errors) == 1, "Expected one error, but got none."
        event = LogEvent({"order": 3}, original=b"")
        dummy_output.store(event)
        assert len(event.errors) == 0, "Expected no error, but got one."

    def test_store_handles_errors(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event = LogEvent({"order": 0}, original=b"")
        dummy_output.store(event)
        assert len(event.errors) == 1, "Expected one error, but got none."

    def test_store_custom_handles_errors(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event = SreEvent(
            {"order": 0},
            state="processed",
            outputs=({"test_instance_name": "stdout"},),
        )
        dummy_output.store_custom(event, target="whatever")
        assert len(event.errors) == 1, "Expected one error, but got none."
