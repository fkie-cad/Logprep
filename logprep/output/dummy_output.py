"""This module contains a dummy output that can be used for testing purposes."""

from typing import List, Type

from logprep.output.output import Output


class DummyOutput(Output):
    """A dummy output that stores unmodified documents unless an exception was raised.

    Parameters
    ----------
    exceptions : list, optional
       A list of exceptions that will be raised.

    """

    def __init__(self, exceptions: List[Type[BaseException]] = None):
        self._exceptions = exceptions if exceptions is not None else []

        self.events = []
        self.failed_events = []
        self.setup_called_count = 0
        self.shut_down_called_count = 0

    def setup(self):
        self.setup_called_count += 1

    def describe_endpoint(self) -> str:
        return "dummy"

    def store(self, document: dict):
        if self._exceptions:
            exception = self._exceptions.pop(0)
            if exception is not None:
                raise exception
        self.events.append(document)

    def store_custom(self, document: dict, target: str):
        self.store(document)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.failed_events.append((error_message, document_received, document_processed))

    def shut_down(self):
        self.shut_down_called_count += 1
