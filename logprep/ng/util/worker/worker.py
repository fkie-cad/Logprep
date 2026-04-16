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
import graphlib
import logging
from asyncio import AbstractEventLoop, CancelledError, QueueEmpty, Task, TaskGroup
from collections import deque
from collections.abc import AsyncIterator, Generator, Iterable, Sequence
from typing import Any, Generic, TypeAlias, TypeVar

from logprep.ng.util.async_helpers import STOP_SENTINEL
from logprep.ng.util.worker.types import AsyncHandler, SizeLimitedQueue

logger = logging.getLogger("Worker")  # pylint: disable=no-member

T = TypeVar("T")
Input = TypeVar("Input")
Output = TypeVar("Output")


WorkerSource: TypeAlias = SizeLimitedQueue[Input] | AsyncIterator[Input]


class Worker(Generic[Input, Output]):
    """
    Generic batching worker.
    """

    def __init__(
        self,
        name: str,
        batch_size: int,
        batch_interval_s: float,
        handler: AsyncHandler[Input],
        in_queue: WorkerSource[Input],
        out_queues: Sequence[SizeLimitedQueue[Output]],
        *,
        drain_in_queue_on_shutdown: bool = False,
    ) -> None:
        self.name = name

        self._handler = handler

        self.in_queue = in_queue
        self.out_queues = out_queues

        self._batch_interval_s = batch_interval_s
        self._batch_size = batch_size

        self._batch_buffer: deque[Input] = deque()
        self._buffer_lock = asyncio.Lock()

        self._flush_timer: asyncio.Task[None] | None = None

        self._drain_in_queue_on_shutdown = drain_in_queue_on_shutdown

    def _start_timer_locked(self) -> None:
        """
        Arm or re-arm the batch timer.

        Must be called with _buffer_lock held. Ensures that at most one
        timer task is active for the current batch window.
        """
        if self._flush_timer:
            if self._flush_timer.done():
                exc = self._flush_timer.exception()
                if exc is not None:
                    logger.error("flush timer task has failed", exc_info=exc)
            else:
                self._flush_timer.cancel()
        self._flush_timer = asyncio.create_task(self._flush_after_interval())

    def _cancel_timer_if_needed(self) -> None:
        """
        Cancel the active timer task if it is still pending.

        Avoids cancelling the currently executing timer task to prevent
        self-cancellation race conditions.
        """
        t = self._flush_timer
        if not t:
            return
        if t.done():
            exc = t.exception()
            if exc is not None:
                logger.error("flush timer task has failed", exc_info=exc)
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

        batch: list[Input] | None = None
        async with self._buffer_lock:
            if self._batch_buffer:
                batch = self._drain_locked()
            if self._flush_timer is asyncio.current_task():
                self._flush_timer = None

        if batch:
            logger.debug("Flushing messages based on timer")
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
            logger.debug("Flushing messages based on backlog size")
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
            logger.debug("Flushing messages based on manual trigger")
            await self._flush_batch(batch_to_flush)

    async def _process_batch(self, batch: list[Input]) -> None:
        await self._handler(batch)

    async def _flush_batch(self, batch: list[Input]) -> None:
        """
        Process and forward a completed batch.

        Applies the optional handler and forwards the resulting items to
        the output queue if configured.
        """
        await self._process_batch(batch)

        await asyncio.sleep(0)

    async def _process_items_continuous(self) -> None:
        match self.in_queue:
            case AsyncIterator():
                while True:
                    item = await anext(self.in_queue)
                    if item == STOP_SENTINEL:
                        break
                    await self.add(item)
                    await asyncio.sleep(1.0)  # HACK to provoke draining
            case SizeLimitedQueue():
                while True:
                    item = await self.in_queue.get()
                    if item == STOP_SENTINEL:
                        break
                    await self.add(item)
                    await asyncio.sleep(1.0)  # HACK to provoke draining

    async def _process_items_exhaustive(self) -> None:
        try:
            match self.in_queue:
                case SizeLimitedQueue():
                    while True:
                        item = self.in_queue.get_nowait()
                        if item == STOP_SENTINEL:
                            break
                        await self.add(item)
                        await asyncio.sleep(0.0)
                case AsyncIterator():
                    while True:
                        item = await anext(self.in_queue)
                        if item == STOP_SENTINEL:
                            break
                        await self.add(item)
                        await asyncio.sleep(0.0)
        except (StopAsyncIteration, QueueEmpty):
            logger.debug("input drained successfully")

    async def run(self) -> None:
        """
        Execute the worker processing loop.

        Continuously consumes items until stop_event is set or the task is
        cancelled. Ensures a final buffer flush during shutdown.
        """

        try:
            logger.debug("Start continuous processing")
            await self._process_items_continuous()
            logger.debug(
                "Stop continuous processing (# remaining in_queue items = %d)",
                self.in_queue.qsize() if isinstance(self.in_queue, SizeLimitedQueue) else None,
            )

        except asyncio.CancelledError:
            logger.error("Worker cancelled")
            raise
        finally:
            pass
            # self._cancel_timer_if_needed()
            # await self.flush()


def create_worker_graph(workers: Iterable[Worker]) -> dict[Worker, Sequence[Worker]]:
    queue2worker: dict[WorkerSource, Worker] = {worker.in_queue: worker for worker in workers}
    return {worker: [queue2worker[queue] for queue in worker.out_queues] for worker in workers}


def iterate_workers_topologically(
    workers: Iterable[Worker],
) -> Generator[Iterable[Worker]]:
    successors = create_worker_graph(workers)
    predecessors = {
        w: [source for source, targets in successors.items() if w in targets] for w in workers
    }
    sorter = graphlib.TopologicalSorter(graph=predecessors)

    sorter.prepare()
    while sorter.is_active():
        nodes = sorter.get_ready()
        yield nodes
        sorter.done(*nodes)


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

        self._worker_tasks: dict[Worker, Task] = {}

        self._exceptions: list[BaseException] = []

    @property
    def _all_worker_tasks(self) -> Sequence[Task]:
        return tuple(self._worker_tasks.values())

    def _create_worker_task(self, worker: Worker, task_group: TaskGroup) -> Task:
        task = task_group.create_task(worker.run(), name=worker.name)
        self._worker_tasks[worker] = task

        def _done(t: asyncio.Task[Any]) -> None:
            assert self._worker_tasks[worker] == task
            del self._worker_tasks[worker]

            logger.debug("worker task %s is finished", worker.name)

            if t.cancelled():
                return

            exc = t.exception()
            if exc is not None:
                logger.error("worker task %s failed due to an exception", exc_info=exc)
                self._exceptions.append(exc)

        task.add_done_callback(_done)
        return task

    async def run(self) -> None:
        """
        Run the manager until stop_event is set.

        Starts workers and background tasks and then blocks waiting for shutdown.
        """

        try:
            async with asyncio.TaskGroup() as tg:
                for worker in self._workers:
                    self._create_worker_task(worker, tg)
        except CancelledError:
            logger.error("orchestrator cancelled; workers are being shut down hard")
            raise

    async def shut_down(self, timeout_s: float) -> None:
        """
        Fully shut down the manager.

        Stops workers and background tasks, clears registrations, and signals stop_event
        so run() can exit.
        """

        logger.debug(
            "waiting %f seconds for termination of %d tasks", timeout_s, len(self._worker_tasks)
        )

        try:
            await asyncio.wait_for(self._stop_workers_in_topological_order(), timeout_s)
        except TimeoutError:
            logger.debug("Encountered TimeoutError")
            unfinished_workers = [t for t in self._all_worker_tasks if not t.done()]
            if unfinished_workers:
                for t in unfinished_workers:
                    t.cancel()
                logger.debug(
                    "[%d/%d] did not stop gracefully. Awaiting cancellation: [%s]",
                    len(unfinished_workers),
                    len(self._all_worker_tasks),
                    ", ".join(map(asyncio.Task.get_name, unfinished_workers)),
                )
                await asyncio.gather(*unfinished_workers, return_exceptions=True)

    async def _stop_workers_in_topological_order(self) -> None:
        group_timeout_s = 5

        logger.debug("Stopping workers in topological order")
        for group in iterate_workers_topologically(self._workers):

            logger.debug("Stopping next worker group: %s", ", ".join(w.name for w in group))
            async with asyncio.TaskGroup() as sentinel_senders:
                for worker in group:
                    if isinstance(worker.in_queue, SizeLimitedQueue):
                        sentinel_senders.create_task(worker.in_queue.put(STOP_SENTINEL))
                    if isinstance(worker.in_queue, AsyncIterator):
                        # TODO inject SENTINEL in in_queue instead
                        self._worker_tasks[worker].cancel()

            logger.debug("Waiting for worker group to stop gracefully")
            group_tasks = [self._worker_tasks[worker] for worker in group]
            try:
                logger.debug("bla")
                for t in group_tasks:
                    logger.debug(
                        "done = %s, cancelled = %s, cancelling = %s",
                        t.done(),
                        t.cancelled(),
                        t.cancelling(),
                    )
                results = await asyncio.wait_for(
                    asyncio.gather(*group_tasks, return_exceptions=True), group_timeout_s
                )
                logger.debug("stopped gracefully")

            except TimeoutError:
                logger.error(
                    "Worker group did not stop gracefully after %f seconds and had to be cancelled",
                    group_timeout_s,
                )
                results = await asyncio.gather(*group_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Exception encountered while stopping worker", exc_info=result)
