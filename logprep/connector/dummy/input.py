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
from functools import cached_property
from typing import List, Optional, Union

from attr import field, validators
from attrs import define

from logprep.abc.input import Input, SourceDisconnectedWarning


class DummyInput(Input):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """DummyInput specific configuration"""

        documents: List[Union[dict, type, Exception]]
        """A list of documents that should be returned."""
        repeat_documents: Optional[str] = field(
            validator=validators.instance_of(bool), default=False
        )
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

    @cached_property
    def _documents(self):
        return copy.copy(self._config.documents)

    def _get_event(self, timeout: float) -> tuple:
        """Retrieve next document from configuration and raise warning if found"""
        if not self._documents:
            if not self._config.repeat_documents:
                raise SourceDisconnectedWarning(self, "no documents left")
            del self.__dict__["_documents"]

        document = self._documents.pop(0)

        if (document.__class__ == type) and issubclass(document, Exception):
            raise document
        return document, None
