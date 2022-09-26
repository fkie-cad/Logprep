"""
DummyInput
==========

A dummy input that returns the documents it was initialized with.

If a "document" is derived from BaseException, that exception will be thrown instead of
returning a document. The exception will be removed and subsequent calls may return documents or
throw other exceptions in the given order.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      mydummyinput:
        type: dummy_input
        documents: [{"document":"one"}, "Exception", {"document":"two"}]
"""
from typing import List, Union
from attrs import define
from logprep.abc.input import Input, SourceDisconnectedError


class DummyInput(Input):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """DummyInput specific configuration"""

        documents: List[Union[dict, type, BaseException]]
        """A list of documents that should be returned."""

    @property
    def _documents(self):
        return self._config.documents

    def _get_event(self, timeout: float) -> tuple:
        """Retriev next document from configuration and raise error if found"""
        if not self._documents:
            raise SourceDisconnectedError

        document = self._documents.pop(0)

        if (document.__class__ == type) and issubclass(document, BaseException):
            raise document
        return document, None
