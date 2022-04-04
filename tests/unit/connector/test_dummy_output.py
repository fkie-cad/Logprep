from pytest import raises, fail

from logprep.output.dummy_output import DummyOutput
from logprep.output.output import FatalOutputError


class TestDummyOutput:
    def test_store_appends_document_to_variable(self):
        output = DummyOutput()
        document = {"the": "document"}
        output.store(document)

        assert len(output.events) == 1
        assert output.events[0] == document

    def test_store_custom_appends_document_to_variable(self):
        output = DummyOutput()
        document = {"the": "document"}
        output.store_custom(document, target="whatever")

        assert len(output.events) == 1
        assert output.events[0] == document

    def test_increments_setup_called_count_when_setup_was_called(self):
        output = DummyOutput()

        assert output.setup_called_count == 0

        output.setup()
        assert output.setup_called_count == 1

    def test_increments_shutdown_called_count_when_shutdown_was_called(self):
        output = DummyOutput()

        assert output.shut_down_called_count == 0

        output.shut_down()
        assert output.shut_down_called_count == 1

    def test_store_maintains_order_of_documents(self):
        output = DummyOutput()
        for i in range(0, 3):
            output.store({"order": i})

        assert len(output.events) == 3
        for order in range(0, 3):
            assert output.events[order]["order"] == order

    def test_raises_exception_on_call_to_store(self):
        output = DummyOutput(exceptions=[FatalOutputError])

        with raises(FatalOutputError):
            output.store({"order": 0})

    def test_raises_exception_on_call_to_store_custom(self):
        output = DummyOutput(exceptions=[FatalOutputError])

        with raises(FatalOutputError):
            output.store_custom({"order": 0}, target="whatever")

    def test_raises_exception_only_once(self):
        output = DummyOutput(exceptions=[FatalOutputError])

        with raises(FatalOutputError):
            output.store({"order": 0})
        try:
            output.store({"order": 0})
        except FatalOutputError:
            fail("Must not raise exception more than once")

    def test_raises_exception_only_when_not_none(self):
        output = DummyOutput(exceptions=[None, FatalOutputError, None])

        output.store({"order": 0})
        with raises(FatalOutputError):
            output.store({"order": 1})
        output.store({"order": 2})

    def test_stores_failed_events_in_respective_list(self):
        output = DummyOutput()
        output.store_failed("message", {"doc": "received"}, {"doc": "processed"})

        assert len(output.failed_events) == 1
        assert output.failed_events[0] == ("message", {"doc": "received"}, {"doc": "processed"})
