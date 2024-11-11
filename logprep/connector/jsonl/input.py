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

import copy
from functools import cached_property

from logprep.connector.json.input import JsonInput
from logprep.util.json_handling import parse_jsonl


class JsonlInput(JsonInput):
    """JsonlInput Connector"""

    @cached_property
    def _documents(self):
        return copy.copy(parse_jsonl(self._config.documents_path))
