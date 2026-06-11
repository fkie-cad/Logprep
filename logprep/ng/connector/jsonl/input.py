"""
JsonlInput
==========

A json line input that returns the documents it was initialized with.

If a "document" is derived from Exception, that exception will be thrown instead of
returning a document. The exception will be removed and subsequent calls may return documents or
throw other exceptions in the given order.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      myjsonlinput:
        type: jsonl_input
        documents_path: path/to/a/document.jsonl
        repeat_documents: true
"""

import typing
from copy import deepcopy

from attrs import define

from logprep.ng.connector.dummy.input import BaseDummyInput
from logprep.util.json_handling import parse_jsonl


class JsonlInput(BaseDummyInput):
    """JsonlInput Connector"""

    @define(kw_only=True)
    class Config(BaseDummyInput.Config):
        """JsonlInput connector specific configuration"""

        documents_path: str
        """A path to a file in jsonl format, which holds event dicts line by line."""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("JsonlInput.Config", self._config)

    async def _produce_documents(self):
        return deepcopy(parse_jsonl(self._config.documents_path))
