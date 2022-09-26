# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import sys
from unittest import mock

from tests.unit.connector.base import BaseOutputTestCase


class TestConsoleOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "console_output",
    }

    def test_describe_returns_console_output(self):
        assert self.object.describe() == f"{self.object.__class__.__name__} (Test Instance Name)"

    @mock.patch("logprep.connector.console.output.pprint")
    def test_store_calls_pprint(self, mock_pprint):
        self.object.store({"message": "mymessage"})
        mock_pprint.assert_called()

    @mock.patch("logprep.connector.console.output.pprint")
    def test_store_calls_pprint_with_message(self, mock_pprint):
        message = {"message": "mymessage"}
        self.object.store(message)
        mock_pprint.assert_called_with(message)

    @mock.patch("logprep.connector.console.output.pprint")
    def test_store_custom_calls_pprint(self, mock_pprint):
        self.object.store_custom({"message": "mymessage"}, target="stdout")
        mock_pprint.assert_called()

    @mock.patch("logprep.connector.console.output.pprint")
    def test_store_custom_calls_pprint_with_message_and_stream(self, mock_pprint):
        message = {"message": "mymessage"}
        self.object.store_custom(message, target="stdout")
        mock_pprint.assert_called_with(message, stream=sys.stdout)

    @mock.patch("logprep.connector.console.output.pprint")
    def test_store_failed_calls_pprint_with_message_on_stderr(self, mock_pprint):
        message = {"message": "mymessage"}
        self.object.store_failed("myerrormessage", message, message)
        mock_pprint.assert_called_with(f"myerrormessage: {message}, {message}", stream=sys.stderr)
