"""
Worker execution and batching mechanics.

This module provides the standalone Worker abstraction responsible for
input consumption, batching, processing,
and cooperative shutdown behavior.

The worker is intentionally decoupled from pipeline orchestration logic
and focuses solely on predictable buffering, flushing, and backpressure
interaction with the output queue.
"""

import asyncio
import graphlib
import logging
from asyncio import AbstractEventLoop, Task
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
    ) -> None:
        self.name = name

        self._handler = handler

        self.in_queue = in_queue
        self.out_queues = out_queues

        self._stop_event = asyncio.Event()

        self._batch_interval_s = batch_interval_s
        self._batch_size = batch_size

        self._batch_buffer: deque[Input] = deque()
        self._buffer_lock = asyncio.Lock()

        self._flush_timer: asyncio.Task[None] | None = None

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
        self._flush_timer = asyncio.create_task(
            self._flush_after_interval(), name=f"{self.name}-flush_timer"
        )

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

    def __repr__(self):
        elements = [self.name, f"#buffer={len(self._batch_buffer)}"]
        if isinstance(self.in_queue, SizeLimitedQueue):
            elements.append(f"#queue={self.in_queue.qsize()}")
        return f"Worker({', '.join(elements)})"

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

    async def _process_items(self) -> None:
        match self.in_queue:
            case AsyncIterator():
                while not self._stop_event.is_set():
                    item = await anext(self.in_queue)
                    if item == STOP_SENTINEL:
                        break
                    await self.add(item)
                    await asyncio.sleep(0.0)
            case SizeLimitedQueue():
                while True:
                    item = await self.in_queue.get()
                    if item == STOP_SENTINEL:
                        break
                    await self.add(item)
                    await asyncio.sleep(0.0)
            case _:
                raise TypeError(f"Unexpected in_queue type {type(self.in_queue)}")

    async def run(self) -> None:
        """
        Execute the worker processing loop.

        Continuously consumes items until stop_event is set or the task is
        cancelled. Ensures a final buffer flush during shutdown.
        """

        try:
            logger.debug("Start continuous processing")
            await self._process_items()

        except StopAsyncIteration:
            logger.debug("Worker stopped due to exhausted input")
        finally:
            self._cancel_timer_if_needed()
            await self.flush()

    async def stop(self) -> None:
        """Issues the worker to stop. The stopping worker has to be awaited separately."""
        match (self.in_queue):
            case SizeLimitedQueue():
                await self.in_queue.put(STOP_SENTINEL)  # type: ignore
            case AsyncIterator():
                self._stop_event.set()
            case _:
                raise TypeError(f"Unexpected in_queue type {type(self.in_queue)}")


def create_worker_graph(workers: Iterable[Worker]) -> dict[Worker, Sequence[Worker]]:
    """
    Translates workers with their `in_queue` and `out_queues` into a data-flow graph
    representation where each worker is mapped to its successor workers.

    Parameters
    ----------
    workers : Iterable[Worker]
        Workers to create the graph from

    Returns
    -------
    dict[Worker, Sequence[Worker]]
        A mapping between each `Worker` and its sucessors in the data flow
    """
    queue2worker: dict[WorkerSource, Worker] = {worker.in_queue: worker for worker in workers}
    return {worker: [queue2worker[queue] for queue in worker.out_queues] for worker in workers}


def iterate_workers_topologically(
    workers: Iterable[Worker],
) -> Generator[Iterable[Worker]]:
    """
    Iterate workers in topological order from source to sink.
    Workers are processed in groups, whereas each yielded group contains exactly those workers
    whose predecessors have all been processed already.

    Parameters
    ----------
    workers : Iterable[Worker]
        Workers to iterate topologically

    Yields
    ------
    Generator[Iterable[Worker]]
        Generator yielding groups of workers for which all of their parents have been processed before
    """
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

    @property
    def _all_queues(self) -> Sequence[SizeLimitedQueue]:
        return [
            worker.in_queue
            for worker in self._workers
            if isinstance(worker.in_queue, SizeLimitedQueue)
        ]

    def _create_worker_task(self, worker: Worker) -> Task:
        task = self._loop.create_task(worker.run(), name=worker.name)
        self._worker_tasks[worker] = task

        def _done(t: asyncio.Task[Any]) -> None:
            assert self._worker_tasks[worker] == task
            del self._worker_tasks[worker]

            logger.debug("Worker task %s is finished", worker.name)

            if t.cancelled():
                return

            exc = t.exception()
            if exc is not None:
                logger.error("Worker task %s failed due to an exception", exc_info=exc)
                self._exceptions.append(exc)

        task.add_done_callback(_done)
        return task

    def _create_worker_tasks(self):
        return [self._create_worker_task(worker) for worker in self._workers]

    async def run(self, stop_event: asyncio.Event, graceful_shutdown_timeout_s: float) -> None:
        """
        Start worker tasks and wait for them to finish.
        """

        assert not self._worker_tasks

        logger.debug("Starting workers: %s", self._get_current_state())

        self._create_worker_tasks()

        await stop_event.wait()

        logger.debug("Stopping workers gracefully: %s", self._get_current_state())

        await self._shut_down(graceful_shutdown_timeout_s)

        logger.debug("Workers stopped: %s", self._get_current_state())

        # try:
        #     raise_from_gather(
        #         await asyncio.gather(
        #             *(self._create_worker_task(worker) for worker in self._workers),
        #             return_exceptions=True,
        #         ),
        #         "worker tasks exited with errors",
        #     )
        # except CancelledError:
        #     logger.exception("Orchestrator has been cancelled externally; shutting down hard")
        #     raise

    async def _shut_down(self, timeout_s: float) -> None:
        """
        Fully shut down the manager.

        Stops workers and background tasks, clears registrations, and signals stop_event
        so run() can exit.
        """

        logger.debug(
            "Waiting %f seconds for termination of %d tasks", timeout_s, len(self._worker_tasks)
        )

        try:
            await asyncio.wait_for(
                # wait_for spawns a task either way, let's do it ourselves and give it a name
                self._loop.create_task(
                    self._stop_workers_in_topological_order(), name="orchestrator-shut_down"
                ),
                timeout_s,
            )
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
            await asyncio.gather(*(worker.stop() for worker in group))

            logger.debug("Waiting for worker group to stop gracefully")
            group_tasks = [
                self._worker_tasks[worker] for worker in group if worker in self._worker_tasks
            ]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*group_tasks, return_exceptions=True), group_timeout_s
                )

            except TimeoutError:
                logger.error(
                    "Worker group did not stop gracefully after %f seconds and had to be cancelled",
                    group_timeout_s,
                )
                results = await asyncio.gather(*group_tasks, return_exceptions=True)

            errors = [result for result in results if isinstance(result, Exception)]
            if errors:
                raise ExceptionGroup("Exceptions encountered while stopping workers", errors)

    def _get_current_state(self) -> str:
        return ", ".join(map(str, self._workers))
