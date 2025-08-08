# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import copy

import pytest

from logprep.factory import Factory
from logprep.ng.abc.input import SourceDisconnectedWarning
from tests.unit.ng.connector.base import BaseInputTestCase


class DummyError(Exception):
    pass


class TestDummyInput(BaseInputTestCase):
    timeout = 0.01

    CONFIG = {"type": "ng_dummy_input", "documents": []}

    def test_fails_with_disconnected_error_if_input_was_empty(self):
        config = copy.deepcopy(self.CONFIG)
        connector = Factory.create({"Test Instance Name": config})
        connector.setup()

        with pytest.raises(SourceDisconnectedWarning):
            connector.get_next(self.timeout)

    def test_returns_documents_in_order_provided(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]

        connector = Factory.create({"Test Instance Name": config})
        connector.setup()

        for order in range(0, 3):
            event = connector.get_next(self.timeout)
            assert event.data.get("order") == order

    def test_raises_exceptions_instead_of_returning_them_in_document(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [{"order": 0}, DummyError, {"order": 1}]
        connector = Factory.create({"Test Instance Name": config})
        connector.setup()

        event = connector.get_next(self.timeout)

        assert event.data.get("order") == 0

        with pytest.raises(DummyError):
            _, _ = connector.get_next(self.timeout)

        event = connector.get_next(self.timeout)
        assert event.data.get("order") == 1

    def test_raises_exceptions_instead_of_returning_them(self):
        config = copy.deepcopy(self.CONFIG)
        config["documents"] = [Exception]
        connector = Factory.create({"Test Instance Name": config})

        with pytest.raises(Exception):
            connector.get_next(self.timeout)

    def test_repeat_documents_repeats_documents(self):
        config = copy.deepcopy(self.CONFIG)
        config["repeat_documents"] = True
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]
        connector = Factory.create(configuration={"Test Instance Name": config})
        connector.setup()

        for order in range(0, 9):
            event = connector.get_next(self.timeout)
            assert event.data.get("order") == order % 3

    def test_dummy_input_iterator(self):
        config = copy.deepcopy(self.CONFIG)
        config["repeat_documents"] = False
        config["documents"] = [{"order": 0}, {"order": 1}, {"order": 2}]
        dummy_input_connector = Factory.create({"Test Instance Name": config})
        dummy_input_connector.setup()

        with pytest.raises(SourceDisconnectedWarning):
            dummy_input_iterator = dummy_input_connector(timeout=self.timeout)

            assert next(dummy_input_iterator).data == {"order": 0}
            assert next(dummy_input_iterator).data == {"order": 1}
            assert next(dummy_input_iterator).data == {"order": 2}
            assert next(dummy_input_iterator) is None
