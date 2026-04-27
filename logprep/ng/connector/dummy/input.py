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
        documents: [{"document":"one"}, {"document":"two"}]
"""

import asyncio
import typing
from collections.abc import Sequence
from copy import deepcopy

from attrs import define, field, validators

from logprep.ng.abc.input import Input
from logprep.ng.event.log_event import LogEvent


class DummyInput(Input):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """DummyInput specific configuration"""

        documents: Sequence[LogEvent | BaseException]
        """A list of documents that should be returned."""
        repeat_documents: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("DummyInput.Config", self._config)

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self._documents = list(map(deepcopy, self.config.documents))
        self._acked_events: list[LogEvent] = []
        self._empty_event = asyncio.Event()

    async def setup(self):
        if not self._documents:
            self._empty_event.set()
        return await super().setup()

    async def _get_event(self, timeout):
        raise NotImplementedError()

    async def get_next(self, timeout: float) -> LogEvent | None:
        """Retrieve next document from configuration and raise warning if found"""

        if not self._documents:
            raise StopAsyncIteration("no documents left")

        document = self._documents.pop(0)

        if not self._documents:
            if self.config.repeat_documents:
                self._documents = list(map(deepcopy, self.config.documents))
            else:
                self._empty_event.set()

        if isinstance(document, BaseException):
            raise document

        return deepcopy(document)

    async def acknowledge(self, events):
        self._acked_events.extend(events)

    @property
    def empty_event(self) -> asyncio.Event:
        """Returns an event primitive signaling that all configured events where consumed"""
        return self._empty_event

    @property
    def acknowledged_events(self) -> Sequence[LogEvent]:
        """Return events which have been presented through the `acknowledge` method"""
        return self._acked_events
