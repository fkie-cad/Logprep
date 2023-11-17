# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import copy

from pytest import raises

from logprep.abc.input import SourceDisconnectedWarning
from logprep.factory import Factory
from tests.unit.connector.base import BaseInputTestCase


class DummyError(BaseException):
    pass


class TestDummyInput(BaseInputTestCase):
    timeout = 0.01

    CONFIG = {"type": "dummy_input", "documents": []}

    def test_fails_with_disconnected_error_if_input_was_empty(self):
        with raises(SourceDisconnectedWarning):
            self.object.get_next(self.timeout)

    def test_returns_documents_in_order_provided(self):
        self.object._config.documents = [{"order": 0}, {"order": 1}, {"order": 2}]
        for order in range(0, 3):
            event, _ = self.object.get_next(self.timeout)
            assert event.get("order") == order

    def test_raises_exceptions_instead_of_returning_them_in_document(self):
        self.object._config.documents = [{"order": 0}, DummyError, {"order": 1}]
        event, _ = self.object.get_next(self.timeout)
        assert event.get("order") == 0
        with raises(DummyError):
            _, _ = self.object.get_next(self.timeout)
        event, _ = self.object.get_next(self.timeout)
        assert event.get("order") == 1

    def test_raises_exceptions_instead_of_returning_them(self):
        self.object._config.documents = [BaseException]
        with raises(BaseException):
            self.object.get_next(self.timeout)

    def test_repeat_documents_repeats_documents(self):
        config = copy.deepcopy(self.CONFIG)
        config["repeat_documents"] = True
        connector = Factory.create(configuration={"Test Instance Name": config}, logger=self.logger)
        connector._config.documents = [{"order": 0}, {"order": 1}, {"order": 2}]

        for order in range(0, 9):
            event, _ = connector.get_next(self.timeout)
            assert event.get("order") == order % 3
