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
from collections.abc import Callable, Coroutine
from typing import TypeVar

T = TypeVar("T")
Input = TypeVar("Input")
Output = TypeVar("Output")

SyncHandler = Callable[[list[Input]], list[Output]]
AsyncHandler = Callable[[list[Input]], Coroutine[object, object, list[Output]]]
Handler = SyncHandler[Input, Output] | AsyncHandler[Input, Output]


class SizeLimitedQueue(asyncio.Queue[T]):
    """
    Queue wrapper which ensures a maxsize configured.

    Parameters
    ----------
    maxsize : int
        Maximum number of items the queue can hold.
        Must be > 0.

    Raises
    ------
    ValueError
        If maxsize <= 0.
    """

    def __init__(self, maxsize: int) -> None:
        if maxsize <= 0:
            raise ValueError("Queue must be bounded")
        super().__init__(maxsize=maxsize)
