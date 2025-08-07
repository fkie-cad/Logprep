# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-statements
# pylint: disable=too-many-lines

from unittest import mock

from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.connector.base import BaseOutputTestCase


class TestConsoleOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "ng_console_output",
    }

    def test_describe_returns_console_output(self):
        assert self.object.describe() == f"{self.object.__class__.__name__} (Test Instance Name)"

    @mock.patch("logprep.ng.connector.console.output.pprint")
    def test_store_calls_pprint(self, mock_pprint):
        event = LogEvent({"message": "mymessage"}, original=b"")
        self.object.store(event)
        mock_pprint.assert_called()

    @mock.patch("logprep.ng.connector.console.output.pprint")
    def test_store_calls_pprint_with_message(self, mock_pprint):
        message = {"message": "mymessage"}
        event = LogEvent(message, original=b"")
        self.object.store(event)
        mock_pprint.assert_called_with(message)

    @mock.patch("logprep.ng.connector.console.output.pprint")
    def test_store_custom_calls_pprint(self, mock_pprint):
        event = LogEvent({"message": "mymessage"}, original=b"", state=EventStateType.PROCESSED)
        self.object.store_custom(event, target="stdout")
        mock_pprint.assert_called()

    def test_store_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch("logprep.ng.connector.console.output.pprint") as mocked_function:
            mocked_function.side_effect = Exception("Test exception")
            self.object.store(event)
        mocked_function.assert_called()
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch("logprep.ng.connector.console.output.pprint") as mocked_function:
            mocked_function.side_effect = Exception("Test exception")
            self.object.store_custom(event, "stdout")
        mocked_function.assert_called()
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_store_handles_errors_failed_event(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch("logprep.ng.connector.console.output.pprint") as mocked_function:
            mocked_function.side_effect = Exception("Test exception")
            self.object.store(event)
        mocked_function.assert_called()
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors_failed_event(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch("logprep.ng.connector.console.output.pprint") as mocked_function:
            mocked_function.side_effect = Exception("Test exception")
            self.object.store_custom(event, "stdout")
        mocked_function.assert_called()
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"
