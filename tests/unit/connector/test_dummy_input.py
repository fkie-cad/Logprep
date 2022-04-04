from pytest import raises

from logprep.input.dummy_input import DummyInput
from logprep.input.input import SourceDisconnectedError


class DummyError(BaseException):
    pass


class TestDummyInput:
    timeout = 0.01

    def setup_class(self):
        self.input = DummyInput([])

    def test_describe_endpoint_returns_dummy(self):
        assert self.input.describe_endpoint() == "dummy"

    def test_fails_with_disconnected_error_if_input_was_empty(self):
        with raises(SourceDisconnectedError):
            self.input.get_next(self.timeout)

    def test_increments_setup_called_count_when_setup_was_called(self):
        assert self.input.setup_called_count == 0

        self.input.setup()
        assert self.input.setup_called_count == 1

    def test_increments_shutdown_called_count_when_shutdown_was_called(self):
        assert self.input.shut_down_called_count == 0

        self.input.shut_down()
        assert self.input.shut_down_called_count == 1

    def test_returns_documents_in_order_provided(self):
        documents = [{"order": 0}, {"order": 1}, {"order": 2}]
        dummy_input = DummyInput(documents)

        for order in range(0, 3):
            assert dummy_input.get_next(self.timeout)["order"] == order
        with raises(SourceDisconnectedError):
            dummy_input.get_next(self.timeout)

    def test_raises_exceptions_instead_of_returning_them(self):
        documents = [{"order": 0}, DummyError, {"order": 1}]
        dummy_input = DummyInput(documents)

        assert dummy_input.get_next(self.timeout)["order"] == 0
        with raises(DummyError):
            dummy_input.get_next(self.timeout)
        assert dummy_input.get_next(self.timeout)["order"] == 1

        with raises(SourceDisconnectedError):
            dummy_input.get_next(self.timeout)
