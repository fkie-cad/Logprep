"""This module contains a dummy input that can be used for testing purposes."""


from functools import cached_property
from logprep.abc.input import CriticalInputError, Input, SourceDisconnectedError
from logprep.util.json_handling import parse_json


class JsonInput(Input):
    """A json input that returns the documents it was initialized with.

    If a "document" is derived from BaseException, that exception will be thrown instead of
    returning a document. The exception will be removed and subsequent calls may return documents or
    throw other exceptions in the given order.

    Parameters
    ----------
    documents_path : string
       A path to a file in json format with json dicts in a list.

    """

    class Config(Input.Config):
        documents_path: str

    __slots__ = ["last_timeout"]

    last_timeout: float

    @cached_property
    def _documents(self):
        return parse_json(self._config.documents_path)

    def describe_endpoint(self) -> str:
        return "json"

    def get_next(self, timeout: float) -> dict:
        self.last_timeout = timeout
        if not self._documents:
            raise SourceDisconnectedError

        document = self._documents.pop(0)

        if not isinstance(document, dict):
            raise CriticalInputError("not a dict", document)
        return document
