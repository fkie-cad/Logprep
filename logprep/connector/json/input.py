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

import copy
from functools import cached_property
from typing import Optional

from attr import field, validators
from attrs import define

from logprep.abc.input import Input
from logprep.connector.dummy.input import DummyInput
from logprep.util.json_handling import parse_json


class JsonInput(DummyInput):
    """JsonInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """JsonInput connector specific configuration"""

        documents_path: str
        """A path to a file in json format, with can also include multiple jsons
        dicts wrapped in a list."""
        repeat_documents: Optional[bool] = field(
            validator=validators.instance_of(bool), default=False
        )
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

    @cached_property
    def _documents(self):
        return copy.copy(parse_json(self._config.documents_path))
