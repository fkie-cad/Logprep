"""
Pipeline-aware worker specialization.

This module defines PipelineWorker, a Worker variant that resolves its batch
handler dynamically via a HandlerResolver. This enables late binding of handler
implementations, supports reload/rebind scenarios, and keeps workers reusable
outside of a concrete pipeline manager.
"""

from typing import Any, Generic, TypeVar

from async_pipeline.types import AsyncHandler, Handler, HandlerResolver, SyncHandler
from async_pipeline.worker.worker import Worker

T = TypeVar("T")


class PipelineWorker(Worker[T], Generic[T]):
    """
    Worker that resolves its handler dynamically via a HandlerResolver.

    A PipelineWorker stores a logical handler identifier instead of a direct
    callable. The handler is resolved lazily at runtime and cached until the
    resolver is re-bound.

    This keeps the worker decoupled from concrete handler implementations while
    preserving the batching and forwarding semantics of the base Worker.
    """

    def __init__(
        self,
        *args: Any,
        handler_name: str,
        handler_resolver: HandlerResolver | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize a pipeline-bound worker.

        Parameters
        ----------
        handler_name:
            Logical handler identifier used for resolution via the resolver.

        handler_resolver:
            Optional resolver to bind immediately. If omitted, a resolver must be
            provided via bind_resolver() before the first flush.
        """
        super().__init__(*args, **kwargs)
        self._handler_name = handler_name
        self._handler_resolver: HandlerResolver | None = None
        self._resolved_handler: AsyncHandler[T] | SyncHandler[T] | None = None

        if handler_resolver is not None:
            self.bind_resolver(handler_resolver)

    def bind_resolver(self, handler_resolver: HandlerResolver) -> None:
        """
        Bind a resolver used to resolve the configured handler name.

        Rebinding clears any cached resolved handler so subsequent flushes will
        resolve again against the new resolver.
        """
        # Fail fast: must be a real subclass of the ABC
        if not isinstance(handler_resolver, HandlerResolver):
            raise TypeError(
                f"handler_resolver must be an instance of HandlerResolver (ABC). "
                f"Got: {type(handler_resolver).__name__}"
            )

        self._handler_resolver = handler_resolver
        self._resolved_handler = None

    def _ensure_resolved_handler(self) -> AsyncHandler[T] | SyncHandler[T]:
        """
        Resolve and cache the handler for this worker.

        Returns a callable matching the handler contract. Resolution is performed
        once per binding and cached until bind_resolver() is called again.
        """
        if self._resolved_handler is not None:
            return self._resolved_handler

        if self._handler_resolver is None:
            raise RuntimeError(
                f"PipelineWorker {self.name!r} requires a resolver to resolve {self._handler_name!r}."
            )

        handler: Handler = self._handler_resolver.resolve(self._handler_name)

        if not callable(handler):
            raise TypeError(f"Resolved handler {self._handler_name!r} is not callable")

        self._resolved_handler = handler
        return self._resolved_handler

    async def _flush_batch(self, batch: list[T]) -> None:
        """
        Flush a batch using a lazily resolved handler.

        Ensures the handler is resolved before delegating to the base Worker
        flush implementation.
        """
        self._handler = self._ensure_resolved_handler()
        await super()._flush_batch(batch)
