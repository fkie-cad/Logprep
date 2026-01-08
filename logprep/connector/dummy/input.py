"""
DummyInput
==========

A dummy input that returns the documents it was initialized with.

If a "document" is derived from Exception, that exception will be thrown instead of
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

import copy
import typing
from functools import cached_property

from attrs import define, field, validators

from logprep.abc.input import Input, SourceDisconnectedWarning


class DummyInput(Input):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """DummyInput specific configuration"""

        documents: list[dict | type | Exception]
        """A list of documents that should be returned."""
        repeat_documents: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast("DummyInput.Config", self._config)

    @cached_property
    def _documents(self) -> list[dict | type | Exception]:
        return copy.deepcopy(self.config.documents)

    def _get_event(self, timeout: float) -> tuple:
        """Retrieve next document from configuration and raise warning if found"""

        if not self._documents:
            if not self.config.repeat_documents:
                raise SourceDisconnectedWarning(self, "no documents left")
            del self.__dict__["_documents"]

        document = self._documents.pop(0)

        if isinstance(document, type) and issubclass(document, Exception):
            raise document

        return document, None
