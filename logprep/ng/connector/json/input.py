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
import typing
from functools import cached_property

from attrs import define, field, validators

from logprep.ng.abc.input import Input
from logprep.ng.connector.dummy.input import DummyInput
from logprep.util.json_handling import parse_json


class JsonInput(DummyInput):
    """JsonInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """JsonInput connector specific configuration"""

        documents_path: str
        """A path to a file in json format, with can also include multiple jsons
        dicts wrapped in a list."""
        repeat_documents: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

    @cached_property
    def _documents(self) -> list:
        # we can not use the config property here, as our config does not inherit the parent config
        config = typing.cast("JsonInput.Config", self._config)
        return copy.copy(parse_json(config.documents_path))
