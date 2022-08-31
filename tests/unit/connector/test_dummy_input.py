# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
from pytest import raises

from logprep.connector.dummy.input import DummyInput
from logprep.abc.input import SourceDisconnectedError
from tests.unit.connector.base import BaseConnectorTestCase


class DummyError(BaseException):
    pass


class TestDummyInput(BaseConnectorTestCase):
    timeout = 0.01

    CONFIG = {"type": "dummy_input", "documents": []}

    def test_fails_with_disconnected_error_if_input_was_empty(self):
        with raises(SourceDisconnectedError):
            self.object.get_next(self.timeout)

    def test_returns_documents_in_order_provided(self):
        self.object._config.documents = [{"order": 0}, {"order": 1}, {"order": 2}]
        for order in range(0, 3):
            assert self.object.get_next(self.timeout)["order"] == order

    def test_raises_exceptions_instead_of_returning_them_in_document(self):
        self.object._config.documents = [{"order": 0}, DummyError, {"order": 1}]
        assert self.object.get_next(self.timeout)["order"] == 0
        with raises(DummyError):
            self.object.get_next(self.timeout)
        assert self.object.get_next(self.timeout)["order"] == 1

    def test_raises_exceptions_instead_of_returning_them(self):
        self.object._config.documents = [BaseException]
        with raises(BaseException):
            self.object.get_next(self.timeout)
