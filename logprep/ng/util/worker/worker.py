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
import logging
from asyncio import AbstractEventLoop
from collections import deque
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from logprep.ng.util.worker.types import AsyncHandler, SizeLimitedQueue

logger = logging.getLogger("Worker")

T = TypeVar("T")
Input = TypeVar("Input")
Output = TypeVar("Output")


class Worker(Generic[Input, Output]):
    """
    Generic batching worker with cooperative shutdown semantics.
    """

    def __init__(
        self,
        name: str,
        batch_size: int,
        batch_interval_s: float,
        handler: AsyncHandler[Input, Output],
        in_queue: asyncio.Queue[Input] | AsyncIterator[Input],
        out_queue: SizeLimitedQueue[Output] | None = None,
    ) -> None:
        self.name = name

        self._handler = handler

        self.in_queue = in_queue
        self.out_queue = out_queue

        self._batch_interval_s = batch_interval_s
        self._batch_size = batch_size

        self._batch_buffer: deque[Input] = deque()
        self._buffer_lock = asyncio.Lock()  # TODO is locking really required?

        self._flush_timer: asyncio.Task[None] | None = None

    def _start_timer_locked(self) -> None:
        """
        Arm or re-arm the batch timer.

        Must be called with _buffer_lock held. Ensures that at most one
        timer task is active for the current batch window.
        """
        if self._flush_timer and not self._flush_timer.done():
            self._flush_timer.cancel()
        self._flush_timer = asyncio.create_task(self._flush_after_interval())

    def _cancel_timer_if_needed(self) -> None:
        """
        Cancel the active timer task if it is still pending.

        Avoids cancelling the currently executing timer task to prevent
        self-cancellation race conditions.
        """
        t = self._flush_timer
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
            logger.debug("timer sleeping")
            await asyncio.sleep(self._batch_interval_s)
        except asyncio.CancelledError:
            logger.debug("timer caught cancelled error")
            return

        batch: list[Input] | None = None
        async with self._buffer_lock:
            if self._batch_buffer:
                batch = self._drain_locked()
            if self._flush_timer is asyncio.current_task():
                self._flush_timer = None

        if batch:
            await self._flush_batch(batch)

    def _drain_locked(self) -> list[Input]:
        """
        Drain the current buffer contents.

        Must be called with _buffer_lock held. Cancels any active timer
        and returns a snapshot of buffered items.
        """
        batch = list(self._batch_buffer)
        self._batch_buffer.clear()
        self._cancel_timer_if_needed()
        self._flush_timer = None
        return batch

    async def add(self, item: Input) -> None:
        """
        Add a single item to the batch buffer.

        May trigger a flush if the size threshold is reached. Starts the
        batch timer when the first item of a new batch arrives.
        """
        batch_to_flush: list[Input] | None = None

        async with self._buffer_lock:
            self._batch_buffer.append(item)

            if len(self._batch_buffer) == 1:
                self._start_timer_locked()

            if len(self._batch_buffer) >= self._batch_size:
                batch_to_flush = self._drain_locked()

        if batch_to_flush:
            await self._flush_batch(batch_to_flush)

    async def flush(self) -> None:
        """
        Force flushing of buffered items.

        Drains and processes the current buffer regardless of size or
        timer state.
        """
        batch_to_flush: list[Input] | None = None
        async with self._buffer_lock:
            if self._batch_buffer:
                batch_to_flush = self._drain_locked()
        if batch_to_flush:
            await self._flush_batch(batch_to_flush)

    async def _process_batch(self, batch: list[Input]) -> list[Output]:
        return await self._handler(batch)

    async def _flush_batch(self, batch: list[Input]) -> None:
        """
        Process and forward a completed batch.

        Applies the optional handler and forwards the resulting items to
        the output queue if configured.
        """
        batch_result: list[Output] = await self._process_batch(batch)

        if self.out_queue is not None:
            for item in batch_result:
                await self.out_queue.put(item)
            await asyncio.sleep(0)

    async def run(self, stop_event: asyncio.Event) -> None:
        """
        Execute the worker processing loop.

        Continuously consumes items until stop_event is set or the task is
        cancelled. Ensures a final buffer flush during shutdown.
        """

        try:
            if isinstance(self.in_queue, asyncio.Queue):
                while not stop_event.is_set():
                    item = await self.in_queue.get()
                    await self.add(item)
                    # TODO is this await really necessary?
                    await asyncio.sleep(0.0)
            else:
                while not stop_event.is_set():
                    item = await anext(self.in_queue)
                    await self.add(item)
                    # TODO is this await really necessary?
                    await asyncio.sleep(0.0)

        except asyncio.CancelledError:
            logger.debug("Worker cancelled")
            raise
        finally:
            await self.flush()


class TransferWorker(Worker[T, T]):
    def __init__(
        self,
        name: str,
        batch_size: int,
        batch_interval_s: float,
        in_queue: asyncio.Queue[T] | AsyncIterator[T],
        out_queue: SizeLimitedQueue[T] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            batch_size=batch_size,
            batch_interval_s=batch_interval_s,
            in_queue=in_queue,
            out_queue=out_queue,
            handler=self.__handle_noop,
        )

    async def __handle_noop(self, batch: list[T]) -> list[T]:
        await asyncio.sleep(0)
        return [e for e in batch if e is not None]


class WorkerOrchestrator:
    """
    Orchestrates a chain of workers.

    Lifecycle:
    - run(): start workers + background tasks and wait until stop_event is set
    - shut_down(): stop workers + background tasks and end manager lifetime
    """

    def __init__(
        self,
        workers: list[Worker],
        loop: AbstractEventLoop | None = None,
    ) -> None:
        """
        Initialize the manager with a worker chain and optional event loop.
        """
        self._loop: AbstractEventLoop = loop if loop is not None else asyncio.get_event_loop()
        self._workers: list[Worker] = workers

        self._stop_event = asyncio.Event()

        self._worker_tasks: set[asyncio.Task[Any]] = set()

        self._exceptions: list[BaseException] = []
        self._reload_lock = asyncio.Lock()

    def _setup(self) -> None:
        """Perform manager initialization steps that require a fully constructed instance."""

    def run_workers(self) -> None:
        """
        Start worker tasks (data-plane).

        Worker tasks may be restarted on reload; background tasks are not.
        """
        for worker in self._workers:
            t = self._loop.create_task(worker.run(self._stop_event), name=worker.name)
            self._add_worker_task(t)

    def _add_worker_task(self, task: asyncio.Task[Any]) -> None:
        """Track a worker task and fail-fast on exceptions."""
        self._worker_tasks.add(task)

        def _done(t: asyncio.Task[Any]) -> None:
            self._worker_tasks.discard(t)

            if t.cancelled():
                return

            exc = t.exception()
            if exc is not None:
                self._exceptions.append(exc)
                self._stop_event.set()

        task.add_done_callback(_done)

    async def run(self) -> None:
        """
        Run the manager until stop_event is set.

        Starts workers and background tasks and then blocks waiting for shutdown.
        """

        self._setup()
        self.run_workers()

        await self._stop_event.wait()

    async def shut_down(self, timeout_s: float) -> None:
        """
        Fully shut down the manager.

        Stops workers and background tasks, clears registrations, and signals stop_event
        so run() can exit.
        """
        self._stop_event.set()

        current_task = asyncio.current_task()
        tasks_but_current = [t for t in self._worker_tasks if t is not current_task]

        logger.debug("waiting for termination of %d tasks", len(tasks_but_current))

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks_but_current, return_exceptions=True), timeout_s
            )
        except TimeoutError:
            unfinished_workers = [w for w in tasks_but_current if not w.done()]
            if len(unfinished_workers) > 0:
                logger.debug(
                    "[%d/%d] did not stop gracefully. Cancelling: [%s]",
                    len(unfinished_workers),
                    len(tasks_but_current),
                    ", ".join(map(asyncio.Task.get_name, unfinished_workers)),
                )
                await asyncio.gather(*tasks_but_current, return_exceptions=True)
