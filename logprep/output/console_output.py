"""This module contains a console output that can be used for testing purposes."""

from pprint import PrettyPrinter

from logprep.output.output import Output


class ConsoleOutput(Output):
    """A console output that pretty prints documents instead of storing them."""

    def __init__(self):
        self._printer = PrettyPrinter()

    def describe_endpoint(self) -> str:
        return "console output"

    def store(self, document: dict):
        self._printer.pprint(document)

    def store_custom(self, document: dict, target: str):
        pass

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        pass
