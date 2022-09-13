"""
JsonInput
=========

A json input that returns the documents it was initialized with.

If a "document" is derived from BaseException, that exception will be thrown instead of
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
"""

import sys

from attrs import define
from logprep.abc.input import Input
from logprep.connector.dummy.input import DummyInput
from logprep.util.json_handling import parse_json

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class JsonInput(DummyInput):
    """JsonInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """JsonInput connector specific configuration"""

        documents_path: str
        """A path to a file in json format, with can also include multiple jsons
        dicts wrapped in a list."""

    @cached_property
    def _documents(self):
        return parse_json(self._config.documents_path)
