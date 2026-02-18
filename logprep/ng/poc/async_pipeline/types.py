"""
Fundamental contracts and abstractions for the async pipeline system.

This module defines the structural interfaces that decouple workers,
handlers, and pipeline infrastructure. The intent is to establish a
clear separation between execution mechanics and processing logic,
allowing components to remain reusable, composable, and reload-safe.

All definitions here describe behavior, expectations, and semantic
constraints rather than implementing runtime functionality.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TypeVar

T = TypeVar("T")

SyncHandler = Callable[[list[T]], list[T]]
AsyncHandler = Callable[[list[T]], Coroutine[object, object, list[T]]]
Handler = SyncHandler[T] | AsyncHandler[T]


class SizeLimitedQueue(asyncio.Queue[T]):
    """
    Bounded asyncio.Queue with explicit semantic intent.

    This subclass exists purely to make queue semantics and typing intent
    explicit within the pipeline architecture.

    Differences from asyncio.Queue:

    - Enforces bounded capacity at construction time.
    - Signals backpressure semantics at the type level.
    - Improves readability by distinguishing pipeline queues from generic queues.

    Parameters
    ----------
    maxsize : int
        Maximum number of items the queue can hold.

        Must be > 0. A non-positive value is rejected to prevent accidental
        creation of unbounded queues, which would break memory budgeting
        and backpressure guarantees.

    Raises
    ------
    ValueError
        If maxsize <= 0.

    Notes
    -----
    - Behavior is otherwise identical to asyncio.Queue.
    - This class introduces no additional synchronization or scheduling logic.
    - Primarily used to encode architectural constraints (memory/backpressure)
      rather than functionality.
    """

    def __init__(self, maxsize: int) -> None:
        if maxsize <= 0:
            raise ValueError("Queue must be bounded")
        super().__init__(maxsize=maxsize)


class HandlerResolver(ABC):
    """
    Resolves handler identifiers to executable handler callables.

    A HandlerResolver provides the indirection layer between pipeline-bound
    components (e.g. PipelineWorker) and the concrete handler implementation.

    Implementations are responsible for mapping a handler name/key to a
    callable object that processes a batch of items.

    Contract:

    - Input:
        name: str
            Logical handler identifier (typically configured on workers).

    - Return:
        Handler
            A callable matching the Handler type contract:

                SyncHandler[T]:  (list[T]) -> list[T]
                AsyncHandler[T]: (list[T]) -> Awaitable[list[T]]

    - Errors:
        AttributeError
            Raised if the handler cannot be resolved.

        TypeError
            Raised if the resolved object is not a valid Handler.

    Notes:

    - Resolution is intentionally dynamic to support late binding, reloads,
      dependency injection, and runtime configuration changes.

    - Implementations may cache results but must remain consistent with
      reload / rebinding semantics of the pipeline system.
    """

    @abstractmethod
    def resolve(self, name: str) -> Handler:
        """Return the handler associated with *name*."""
