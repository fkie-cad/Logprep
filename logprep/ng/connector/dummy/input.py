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
from abc import abstractmethod
from collections.abc import Sequence
from copy import deepcopy

from attrs import define, field, validators

from logprep.ng.abc.event import ErrorEvent, InputMeta, LogEvent
from logprep.ng.abc.input import Input


class BaseDummyInput(Input):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(Input.Config):
        """DummyInput specific configuration"""

        repeat_documents: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`true`, then the given input documents will be repeated after the last
        one is reached. Default: :code:`False`"""

        exhaustable: bool = field(validator=validators.instance_of(bool), default=True)
        """Controls whether the input should stay open (and return `None` internally)
        after consuming all configured documents"""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("BaseDummyInput.Config", self._config)

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self._acked_events: list[LogEvent] = []
        self._empty_event = asyncio.Event()

    @abstractmethod
    async def _produce_documents(
        self,
    ) -> list[
        dict
        | BaseException
        | type
        | typing.Literal["Exception"]
        | typing.Literal["ErrorEvent"]
        | None
    ]:
        """
        Template method for producing the actual documents acting as input data.
        Must always return fresh references.
        """

    async def setup(self):
        self._documents = await self._produce_documents()
        if not self._documents:
            self._empty_event.set()
        return await super().setup()

    async def _get_event(self, timeout: float) -> LogEvent | ErrorEvent | None:
        """Retrieve next document from configuration and raise warning if found"""

        if not self._documents:
            if self.config.exhaustable:
                raise StopAsyncIteration("no documents left")
            else:
                await asyncio.sleep(0)
                return None

        document = self._documents.pop(0)

        if not self._documents:
            if self.config.repeat_documents:
                self._documents = await self._produce_documents()
            else:
                self._empty_event.set()

        match document:
            case BaseException():
                raise document
            case type():
                raise document()
            case str() if document == "Exception":
                raise Exception("something went wrong")
            case str() if document == "ErrorEvent":
                return ErrorEvent({})
            case dict():
                return LogEvent(document, original=b"", input_meta=InputMeta())
            case None:
                return None
            case _:
                raise ValueError("unknown config type")

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


class DummyInput(BaseDummyInput):
    """DummyInput Connector"""

    @define(kw_only=True)
    class Config(BaseDummyInput.Config):
        """DummyInput specific configuration"""

        documents: Sequence[dict | BaseException | type | None]
        """A list of documents that should be returned."""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast("DummyInput.Config", self._config)

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self._documents = list(map(deepcopy, self.config.documents))
        self._acked_events: list[LogEvent] = []
        self._empty_event = asyncio.Event()

    async def _produce_documents(self):
        return list(map(deepcopy, self.config.documents))
