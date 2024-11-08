# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from copy import deepcopy

from pytest import fail, raises

from logprep.abc.output import FatalOutputError
from logprep.factory import Factory
from tests.unit.connector.base import BaseOutputTestCase


class TestDummyOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "dummy_output",
    }

    def test_store_appends_document_to_variable(self):
        document = {"the": "document"}
        self.object.store(document)

        assert len(self.object.events) == 1
        assert self.object.events[0] == document

    def test_store_custom_appends_document_to_variable(self):
        document = {"the": "document"}
        self.object.store_custom(document, target="whatever")

        assert len(self.object.events) == 1
        assert self.object.events[0] == document

    def test_increments_shutdown_called_count_when_shutdown_was_called(self):
        assert self.object.shut_down_called_count == 0
        self.object.shut_down()
        assert self.object.shut_down_called_count == 1

    def test_store_maintains_order_of_documents(self):
        for i in range(0, 3):
            self.object.store({"order": i})
        assert len(self.object.events) == 3
        for order in range(0, 3):
            assert self.object.events[order]["order"] == order

    def test_raises_exception_on_call_to_store(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})

        with raises(Exception, match="FatalOutputError"):
            dummy_output.store({"order": 0})

    def test_raises_exception_on_call_to_store_custom(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})

        with raises(Exception, match="FatalOutputError"):
            dummy_output.store_custom({"order": 0}, target="whatever")

    def test_raises_exception_only_once(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": ["FatalOutputError"]})
        dummy_output = Factory.create({"test connector": config})

        with raises(Exception, match="FatalOutputError"):
            dummy_output.store({"order": 0})
        try:
            dummy_output.store({"order": 0})
        except FatalOutputError:
            fail("Must not raise exception more than once")

    def test_raises_exception_only_when_not_none(self):
        config = deepcopy(self.CONFIG)
        config.update({"exceptions": [None, "FatalOutputError", None]})
        dummy_output = Factory.create({"test connector": config})

        dummy_output.store({"order": 0})
        with raises(Exception, match="FatalOutputError"):
            dummy_output.store({"order": 1})
        dummy_output.store({"order": 2})
