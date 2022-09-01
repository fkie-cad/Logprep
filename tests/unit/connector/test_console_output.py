# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import sys
from unittest import mock

from logprep.connector.console.output import ConsoleOutput


@mock.patch("logprep.connector.console.output.pprint")
class TestConsoleOutput:
    def test_describe_returns_console_output(self, _):
        output = ConsoleOutput()
        assert output.describe_endpoint() == "console output"

    def test_store_calls_pprint(self, mock_pprint):
        output = ConsoleOutput()
        output.store({"message": "mymessage"})
        mock_pprint.assert_called()

    def test_store_calls_pprint_with_message(self, mock_pprint):
        output = ConsoleOutput()
        message = {"message": "mymessage"}
        output.store(message)
        mock_pprint.assert_called_with(message)

    def test_store_custom_calls_pprint(self, mock_pprint):
        output = ConsoleOutput()
        output.store_custom({"message": "mymessage"}, target="stdout")
        mock_pprint.assert_called()

    def test_store_custom_calls_pprint_with_message_and_stream(self, mock_pprint):
        output = ConsoleOutput()
        message = {"message": "mymessage"}
        output.store_custom(message, target="stdout")
        mock_pprint.assert_called_with(message, stream=sys.stdout)

    def test_store_failed_calls_pprint_with_message_on_stderr(self, mock_pprint):
        output = ConsoleOutput()
        message = {"message": "mymessage"}
        output.store_failed("myerrormessage", message, message)
        mock_pprint.assert_called_with(f"myerrormessage: {message}, {message}", stream=sys.stderr)
