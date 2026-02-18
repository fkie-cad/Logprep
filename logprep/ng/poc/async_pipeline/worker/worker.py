"""
Worker execution and batching mechanics.

This module provides the standalone Worker abstraction responsible for
input consumption, deterministic batching, optional batch processing,
and cooperative shutdown behavior.

The worker is intentionally decoupled from pipeline orchestration logic
and focuses solely on predictable buffering, flushing, and backpressure
interaction with the output queue.
"""

import asyncio
import inspect
from collections import deque
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

from async_pipeline.types import AsyncHandler, SizeLimitedQueue, SyncHandler

T = TypeVar("T")


class Worker(Generic[T]):
    """
    Generic batching worker with cooperative shutdown semantics.

    A Worker consumes items from an input source, buffers them into batches
    based on size and/or time thresholds, optionally applies a handler, and
    forwards results to an output queue.

    The worker is intentionally standalone and independent from pipeline
    orchestration logic.

    Responsibilities
    ----------------
    - Input consumption (Queue or AsyncIterator)
    - Size/time-based batching
    - Optional batch processing via handler
    - Output forwarding
    - Graceful cancellation and final flush

    Lifecycle
    ---------
    run()
        Start the worker loop until stop_event is set or the task is cancelled.

    stop_event
        Cooperative shutdown signal used by external coordinators.

    Guarantees
    ----------
    - Buffered items are flushed on cancellation or shutdown.
    - Batch triggers remain deterministic (size vs timer).
    - No implicit threading or scheduling side effects.

    Notes
    -----
    - The worker does not own the event loop.
    - Backpressure behavior is delegated to the output queue.
    - Handler execution may be synchronous or asynchronous.
    """

    def __init__(
        self,
        name: str,
        batch_size: int,
        batch_interval_s: float,
        in_queue: asyncio.Queue[T] | AsyncIterator[T],
        out_queue: SizeLimitedQueue[T] | None = None,
        handler: AsyncHandler[T] | SyncHandler[T] | None = None,
    ) -> None:
        self.name = name

        self.in_queue = in_queue
        self.out_queue = out_queue
        self._handler = handler

        self.stop_event = asyncio.Event()

        self._buffer: deque[T] = deque()
        self._buffer_lock = asyncio.Lock()

        self._timer_task: asyncio.Task[None] | None = None
        self._batch_size = batch_size
        self._batch_interval_s = batch_interval_s

    def _start_timer_locked(self) -> None:
        """
        Arm or re-arm the batch timer.

        Must be called with _buffer_lock held. Ensures that at most one
        timer task is active for the current batch window.
        """
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._flush_after_interval())

    def _cancel_timer_if_needed(self) -> None:
        """
        Cancel the active timer task if it is still pending.

        Avoids cancelling the currently executing timer task to prevent
        self-cancellation race conditions.
        """
        t = self._timer_task
        if not t or t.done():
            return
        if t is asyncio.current_task():
            return
        t.cancel()

    async def _flush_after_interval(self) -> None:
        """
        Timer coroutine responsible for time-based batch flushing.

        Sleeps for the configured interval and flushes the buffered items
        if the batch has not already been drained by the size trigger.
        """
        try:
            await asyncio.sleep(self._batch_interval_s)
        except asyncio.CancelledError:
            return

        batch: list[T] | None = None
        async with self._buffer_lock:
            if self._buffer:
                batch = self._drain_locked()
            if self._timer_task is asyncio.current_task():
                self._timer_task = None

        if batch:
            await self._flush_batch(batch)

    def _drain_locked(self) -> list[T]:
        """
        Drain the current buffer contents.

        Must be called with _buffer_lock held. Cancels any active timer
        and returns a snapshot of buffered items.
        """
        batch = list(self._buffer)
        self._buffer.clear()
        self._cancel_timer_if_needed()
        self._timer_task = None
        return batch

    async def add(self, item: T) -> None:
        """
        Add a single item to the batch buffer.

        May trigger a flush if the size threshold is reached. Starts the
        batch timer when the first item of a new batch arrives.
        """
        batch_to_flush: list[T] | None = None

        async with self._buffer_lock:
            self._buffer.append(item)

            if len(self._buffer) == 1:
                self._start_timer_locked()

            if len(self._buffer) >= self._batch_size:
                batch_to_flush = self._drain_locked()

        if batch_to_flush:
            await self._flush_batch(batch_to_flush)

    async def flush(self) -> None:
        """
        Force flushing of buffered items.

        Drains and processes the current buffer regardless of size or
        timer state.
        """
        batch_to_flush: list[T] | None = None
        async with self._buffer_lock:
            if self._buffer:
                batch_to_flush = self._drain_locked()
        if batch_to_flush:
            await self._flush_batch(batch_to_flush)

    async def _flush_batch(self, batch: list[T]) -> None:
        """
        Process and forward a completed batch.

        Applies the optional handler and forwards the resulting items to
        the output queue if configured.
        """
        batch_result: list[T] = batch

        if self._handler is not None:
            result = self._handler(batch_result)
            if inspect.isawaitable(result):
                batch_result = await result
            else:
                batch_result = result

        if self.out_queue is not None:
            for item in batch_result:
                await self.out_queue.put(item)
            await asyncio.sleep(0)

    async def run(self) -> None:
        """
        Execute the worker processing loop.

        Continuously consumes items until stop_event is set or the task is
        cancelled. Ensures a final buffer flush during shutdown.
        """

        try:
            while not self.stop_event.is_set():
                if isinstance(self.in_queue, asyncio.Queue):
                    item = await self.in_queue.get()
                    try:
                        await self.add(item)
                    finally:
                        self.in_queue.task_done()
                else:
                    item = await anext(self.in_queue)
                    await self.add(item)

        except asyncio.CancelledError:
            pass
        finally:
            await self.flush()
