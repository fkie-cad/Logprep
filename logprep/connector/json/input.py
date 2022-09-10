"""This module contains a dummy input that can be used for testing purposes."""

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
    """A json input that returns the documents it was initialized with.

    If a "document" is derived from BaseException, that exception will be thrown instead of
    returning a document. The exception will be removed and subsequent calls may return documents or
    throw other exceptions in the given order.

    Parameters
    ----------
    documents_path : string
       A path to a file in json format with json dicts in a list.

    """

    @define(kw_only=True)
    class Config(Input.Config):
        documents_path: str

    @cached_property
    def _documents(self):
        return parse_json(self._config.documents_path)
