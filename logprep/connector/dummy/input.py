"""This module contains a dummy input that can be used for testing purposes."""
from typing import List, Union
from attrs import define
from logprep.abc.input import Input, SourceDisconnectedError


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

    @define(kw_only=True)
    class Config(Input.Config):
        documents: List[Union[dict, type, BaseException]]

    @property
    def _documents(self):
        return self._config.documents

    def _get_event(self, timeout: float) -> tuple:
        if not self._documents:
            raise SourceDisconnectedError

        document = self._documents.pop(0)

        if (document.__class__ == type) and issubclass(document, BaseException):
            raise document
        return document, None
