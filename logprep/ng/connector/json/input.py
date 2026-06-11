"""
JsonInput
=========

A json input that returns the documents it was initialized with.

If a "document" is derived from Exception, that exception will be thrown instead of
returning a document. The exception will be removed and subsequent calls may return documents or
throw other exceptions in the given order.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      myjsoninput:
        type: json_input
        documents_path: path/to/a/document.json
        repeat_documents: true
"""

import typing

from attrs import define

from logprep.ng.connector.dummy.input import BaseDummyInput
from logprep.util.json_handling import parse_json


class JsonInput(BaseDummyInput):
    """JsonInput Connector"""

    @define(kw_only=True)
    class Config(BaseDummyInput.Config):
        """JsonInput connector specific configuration"""

        documents_path: str
        """A path to a file in json format, which can also include multiple jsons
        dicts wrapped in a list."""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("JsonInput.Config", self._config)

    async def _produce_documents(self):
        return parse_json(self.config.documents_path)
