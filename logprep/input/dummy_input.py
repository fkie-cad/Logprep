"""This module contains a dummy input that can be used for testing purposes."""

from typing import List, Union
from logprep.input.input import Input, SourceDisconnectedError


class DummyInput(Input):
    """A dummy input that returns the documents it was initialized with.

    If a "document" is derived from BaseException, that exception will be thrown instead of
    returning a document. The exception will be removed and subsequent calls may return documents or
    throw other exceptions in the given order.

    Parameters
    ----------
    documents : list
       A list of documents that should be returned.

    """

    def __init__(self, documents: List[Union[dict, type, BaseException]]):
        self._documents = documents

        self.last_timeout = None
        self.setup_called_count = 0
        self.shut_down_called_count = 0

    def describe_endpoint(self) -> str:
        return "dummy"

    def setup(self):
        self.setup_called_count += 1

    def get_next(self, timeout: float):
        self.last_timeout = timeout
        if not self._documents:
            raise SourceDisconnectedError

        document = self._documents.pop(0)

        if isinstance(document, BaseException):
            raise document
        if (document.__class__ == type) and issubclass(document, BaseException):
            raise document
        return document

    def shut_down(self):
        self.shut_down_called_count += 1
