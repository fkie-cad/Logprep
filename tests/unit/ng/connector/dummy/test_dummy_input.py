# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import copy

import pytest

from logprep.abc.input import SourceDisconnectedWarning
from logprep.factory import Factory
from tests.unit.ng.connector.base import BaseInputTestCase


class DummyError(Exception):
    pass


class TestDummyInput(BaseInputTestCase):
    timeout = 0.01

    CONFIG = {"type": "ng_dummy_input", "documents": []}

    def test_fails_with_disconnected_error_if_input_was_empty(self):
        with pytest.raises(SourceDisconnectedWarning):
            self.object.get_next(self.timeout)

    def test_returns_documents_in_order_provided(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]
        self.object = Factory.create({"Test Instance Name": config})
        for order in range(0, 3):
            event = self.object.get_next(self.timeout)
            assert event.get("order") == order

    def test_raises_exceptions_instead_of_returning_them_in_document(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [{"order": 0}, DummyError, {"order": 1}]
        self.object = Factory.create({"Test Instance Name": config})
        event = self.object.get_next(self.timeout)
        assert event.get("order") == 0
        with pytest.raises(DummyError):
            _, _ = self.object.get_next(self.timeout)
        event = self.object.get_next(self.timeout)
        assert event.get("order") == 1

    def test_raises_exceptions_instead_of_returning_them(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [Exception]
        self.object = Factory.create({"Test Instance Name": config})
        with pytest.raises(Exception):
            self.object.get_next(self.timeout)

    def test_repeat_documents_repeats_documents(self):
        config = copy.deepcopy(self.CONFIG)
        config["repeat_documents"] = True
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]
        connector = Factory.create(configuration={"Test Instance Name": config})

        for order in range(0, 9):
            event = connector.get_next(self.timeout)
            assert event.get("order") == order % 3

    def test_dummy_input_iterator(self):
        config = copy.deepcopy(self.CONFIG)
        config["repeat_documents"] = False
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]
        dummy_input_connector = Factory.create({"Test Instance Name": config})

        with pytest.raises(SourceDisconnectedWarning):
            for i, event in enumerate(dummy_input_connector(timeout=self.timeout)):
                assert event["order"] == i

        assert i == 2
