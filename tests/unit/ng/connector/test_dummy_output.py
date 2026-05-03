# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=useless-option-value

from copy import deepcopy

from logprep.factory import Factory
from logprep.ng.abc.event import OutputSpec
from logprep.ng.connector.dummy.output import DummyOutput
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.sre_event import SreEvent
from tests.unit.ng.connector.base import BaseOutputTestCase


class TestDummyOutput(BaseOutputTestCase[DummyOutput]):
    CONFIG = {
        "type": "ng_dummy_output",
    }

    async def test_store_appends_document_to_variable(self):
        document = {"the": "document"}
        event = LogEvent(document, original=b"")
        await self.object.store_batch([event])

        assert len(self.object.events) == 1
        assert self.object.events[0].data == document

    async def test_store_batch_appends_document_to_variable(self):
        document = {"the": "document"}
        event = LogEvent(document, original=b"")
        await self.object.store_batch([event], target="whatever")

        assert len(self.object.events) == 1
        assert self.object.events[0].data == document

    async def test_increments_shutdown_called_count_when_shutdown_was_called(self):
        assert self.object.shut_down_called_count == 0
        await self.object.shut_down()
        assert self.object.shut_down_called_count == 1

    async def test_store_maintains_order_of_documents(self):
        for i in range(0, 3):
            event = LogEvent({"order": i}, original=b"")
            await self.object.store_batch([event])
        assert len(self.object.events) == 3
        for order in range(0, 3):
            event = self.object.events[order]
            assert event.data["order"] == order

    async def test_raises_exception_on_call_to_store(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})

        event = LogEvent({"order": 0}, original=b"")
        await dummy_output.store_batch([event])
        assert len(event.errors) == 1

    async def test_raises_exception_on_call_to_store_batch(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event = SreEvent(
            {"order": 0},
            outputs=(OutputSpec("test_instance_name", "stdout"),),
        )
        await dummy_output.store_batch([event], target="whatever")
        assert len(event.errors) == 1

    async def test_raises_exception_only_once(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})
        event1 = LogEvent({"order": 0}, original=b"")
        event2 = LogEvent({"order": 0}, original=b"")
        await dummy_output.store_batch([event1])
        await dummy_output.store_batch([event2])
        assert len(event1.errors) == 1, "Expected only one error, but got multiple."
        assert len(event2.errors) == 0, "Expected only one error, but got multiple."

    async def test_raises_exception_only_when_not_none(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": [None, "FatalOutputError", None]})
        dummy_output = Factory.create({"test connector": config})
        event = LogEvent({"order": 0}, original=b"")
        await dummy_output.store_batch([event])
        assert len(event.errors) == 0, "Expected no error, but got one."
        event = LogEvent({"order": 2}, original=b"")
        await dummy_output.store_batch([event])
        assert len(event.errors) == 1, "Expected one error, but got none."
        event = LogEvent({"order": 3}, original=b"")
        await dummy_output.store_batch([event])
        assert len(event.errors) == 0, "Expected no error, but got one."

    async def test_store_batch_handles_errors(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        connector = Factory.create({"Test Instance Name": config})
        connector.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"")
        await connector.store_batch([event], target="custom_target")
        assert connector.metrics.number_of_errors == 1
        assert len(event.errors) == 1

    async def test_store_handles_errors_failed_event(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        connector = Factory.create({"Test Instance Name": config})
        connector.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"")
        await connector.store_batch([event])
        assert connector.metrics.number_of_errors == 1
        assert len(event.errors) == 1

    async def test_store_batch_handles_errors_failed_event(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        connector = Factory.create({"Test Instance Name": config})
        connector.metrics.number_of_errors = 0
        event = LogEvent(
            {"message": "test message"},
            original=b"",
        )
        await connector.store_batch([event], target="custom_target")
        assert connector.metrics.number_of_errors == 1
        assert len(event.errors) == 1

    async def test_do_nothing_does_nothing(self):
        config = deepcopy(self.CONFIG)
        config.update({"do_nothing": True})
        connector = Factory.create({"Test Instance Name": config})
        connector.metrics.number_of_errors = 0
        connector.metrics.number_of_warnings = 0
        connector.metrics.number_of_processed_events = 0
        event = LogEvent({"message": "test message"}, original=b"")
        await connector.store_batch([event], target="custom_target")
        assert connector.metrics.number_of_errors == 0
        assert connector.metrics.number_of_warnings == 0
        assert connector.metrics.number_of_processed_events == 0
        assert len(event.errors) == 0
        assert len(event.warnings) == 0
