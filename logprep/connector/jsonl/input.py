"""
JsonlInput
==========

A json line input that returns the documents it was initialized with.

If a "document" is derived from BaseException, that exception will be thrown instead of
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

"""
import sys
from logprep.connector.json.input import JsonInput
from logprep.util.json_handling import parse_jsonl

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class JsonlInput(JsonInput):
    """JsonlInput Connector"""

    @cached_property
    def _documents(self):
        return parse_jsonl(self._config.documents_path)
