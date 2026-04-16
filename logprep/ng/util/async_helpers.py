"""A collection of helper utilitites for async code"""

import asyncio
import logging
from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Callable,
    Coroutine,
    Sequence,
)
from dataclasses import dataclass
from typing import Any, Awaitable, Generic, Protocol, TypeVar

from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("async_helpers")

T = TypeVar("T")
D = TypeVar("D")
T_co = TypeVar("T_co", covariant=True)

STOP_SENTINEL = object()


class EndlessRunner(Generic[T_co], Protocol):
    async def run(self, stop_event: asyncio.Event) -> T_co: ...


@dataclass
class StoppableTask(Generic[T]):
    """
    A task wrapper for long-running tasks which can be gracefully stopped.
    """

    task: asyncio.Task[T]
    stop: Callable[[], Awaitable[T]]

    def get_name(self) -> str:
        """Calls and returns the result of `get_name` of the underlying task"""
        return self.task.get_name()

    @staticmethod
    def from_runner(
        runner: EndlessRunner[T], task_factory: Callable[[Coroutine], asyncio.Task[T]] | None = None
    ) -> "StoppableTask[T]":
        stop_event = asyncio.Event()

        factory = asyncio.create_task if task_factory is None else task_factory

        task = factory(runner.run(stop_event))

        return StoppableTask.from_event(task, stop_event)

    @staticmethod
    def from_event(task: asyncio.Task[T], stop_event: asyncio.Event) -> "StoppableTask[T]":

        async def _stop():
            stop_event.set()
            await asyncio.shield(task)

        return StoppableTask(task, _stop)

    async def stop_on_event(self, event: asyncio.Event) -> None:
        logger.debug("waiting for event to stop task")
        await event.wait()
        logger.debug("event received. stopping")
        await self.stop()
        logger.debug("event received. stopped")


TaskFactory = Callable[[D], Awaitable[asyncio.Task[T]]]
StoppableTaskFactory = Callable[[D], Awaitable[StoppableTask[T]]]


class StoppableAsyncIterator(AsyncIterator):

    def stop(self):
        pass


class TerminateTaskGroup(Exception):
    """Exception raised to terminate a task group."""

    @staticmethod
    async def raise_on_timeout(timeout_s: float, msg: str | None = None):
        """Raises this exception type as soon as the timeout (in seconds) expires.

        Parameters
        ----------
        timeout_s : float
            Number of seconds after which the exception should be raised
        msg : str | None, optional
            Message for the exception, by default None

        Raises
        ------
        TerminateTaskGroup
            The exception for terminating the task group.
        """
        await asyncio.sleep(timeout_s)
        raise TerminateTaskGroup(msg)

    @staticmethod
    async def raise_on_event(event: asyncio.Event, msg: str | None = None):
        """Raises this exception type as soon as the event is set.

        Parameters
        ----------
        event : asyncio.Event
            Triggering event for the exception
        msg : str | None, optional
            Message for the exception, by default None

        Raises
        ------
        TerminateTaskGroup
            The exception for terminating the task group.
        """
        await event.wait()
        raise TerminateTaskGroup(msg)


def raise_from_gather(gather_results: Sequence[Any | Exception], message: str) -> None:
    exceptions = [r for r in gather_results if isinstance(r, Exception)]
    if exceptions:
        raise ExceptionGroup(message, exceptions)


async def cancel_task_and_wait(task: asyncio.Task[T], timeout_s: float) -> None:
    """Cancels the given task and waits for it to actually stop.
    Raises a :code:`TimeoutError` if timeout expires.
    A :code:`CancelledError` will only be raised if the parent task is cancelled.

    Parameters
    ----------
    task : asyncio.Task[T]
        The task to cancel
    timeout_s : float
        The timeout in seconds to wait

    Raises
    ------
    TimeoutError
        Raised if the timeout expires and the task is still not done.
    """
    task.cancel()
    done, _ = await asyncio.wait([task], timeout=timeout_s)
    if not done:
        raise TimeoutError(f"Task {task.get_name()} did not stop in time after cancellation")


async def restart_task_on_iter(
    source: AsyncIterator[D] | AsyncIterable[D],
    task_factory: TaskFactory[D, T],
    cancel_timeout_s: float | None = None,
    initial_task: asyncio.Task[T] | None = None,
) -> AsyncGenerator[asyncio.Task[T], None]:
    """Consumes an iterable data source and ensures that there is always one task executing on the latest data.

    Parameters
    ----------
    source : AsyncIterator[D] | AsyncIterable[D]
        The data source producing parameters for the spawned tasks
    task_factory : Callable[[D], asyncio.Task[T]]
        The factory to create new tasks from new data items
    cancel_timeout_s : float
        The number of seconds after which task cancellation is deemed not successful
    inital_task : asyncio.Task[T] | None, optional
        The initial task, by default None

    Returns
    -------
    AsyncGenerator[asyncio.Task[T], None]
        The stream of tasks which result from spawning fresh tasks on new data

    Yields
    ------
    Iterator[AsyncGenerator[asyncio.Task[T], None]]
        The stream of tasks which result from spawning fresh tasks on new data
    """
    task = initial_task
    async for data in source:
        if task is not None:
            try:
                match (task):
                    case asyncio.Task() if cancel_timeout_s is None:
                        task.cancel()
                        await task
                    case asyncio.Task() if cancel_timeout_s is not None:
                        await cancel_task_and_wait(task, cancel_timeout_s)
            except asyncio.CancelledError:
                logger.debug("Task cancelled successfully")
        task = await task_factory(data)
        yield task


async def restart_stoppable_task_on_iter(
    source: AsyncIterator[D] | AsyncIterable[D],
    task_factory: StoppableTaskFactory[D, T],
    cancel_timeout_s: float | None = None,
    initial_task: StoppableTask[T] | None = None,
) -> AsyncGenerator[StoppableTask[T], None]:
    """Consumes an iterable data source and ensures that there is always one task executing on the latest data.

    Parameters
    ----------
    source : AsyncIterator[D] | AsyncIterable[D]
        The data source producing parameters for the spawned tasks
    task_factory : StoppableTaskFactory[D, T]
        The factory to create new tasks from new data items
    cancel_timeout_s : float
        The number of seconds after which task cancellation is deemed not successful
    inital_task : StoppableTask[T] | None, optional
        The initial task, by default None

    Returns
    -------
    AsyncGenerator[StoppableTask[T], None]
        The stream of tasks which result from spawning fresh tasks on new data

    Yields
    ------
    Iterator[AsyncGenerator[StoppableTask[T], None]]
        The stream of tasks which result from spawning fresh tasks on new data
    """
    task = initial_task
    async for data in source:
        if task is not None:
            try:
                await asyncio.wait_for(task.stop(), cancel_timeout_s)
            except TimeoutError:
                logger.debug("task cancelled due to timeout")
                # task canceled, wait to stop
                await task.task
        task = await task_factory(data)
        yield task


def asyncio_exception_handler(
    loop: asyncio.AbstractEventLoop,  # pylint: disable=unused-argument
    context: dict,
    logger: logging.Logger,
) -> None:
    """
    Handle unhandled exceptions reported by the asyncio event loop.

    Covers exceptions from background tasks, callbacks, and loop internals.
    Does not handle exceptions from awaited coroutines (e.g. runner.run()).

    Args:
        loop: The current event loop.
        context: Asyncio error context (may contain message, exception, task/future).
        logger: Logger used to record the error.
    """

    msg = context.get("message", "Unhandled exception in event loop")
    exception = context.get("exception")
    task = context.get("task") or context.get("future")

    logger.error(f"{msg}")

    if task:
        logger.error(f"Task: {task!r}")

        if isinstance(task, asyncio.Task):
            logger.error(f"Task name: {task.get_name()}")

    if exception:
        logger.error(f"Unhandled exception: {exception!r}", exc_info=exception)
    else:
        logger.error(f"Context: {context!r}")


async def report_event_state(logger: logging.Logger, batch: list[LogEvent]) -> list[LogEvent]:
    # events_by_state = partition_by_state(batch)
    # logger.info(
    #     "Finished processing %d events: %s",
    #     len(batch),
    #     ", ".join(f"#{state}={len(events)}" for state, events in events_by_state.items()),
    # )
    logger.debug("#events = %d", len(batch))
    return batch
