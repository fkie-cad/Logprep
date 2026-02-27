"""A collection of helper utilitites for async code"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Callable
from typing import TypeVar

T = TypeVar("T")
D = TypeVar("D")


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
    task_factory: Callable[[D], asyncio.Task[T]],
    cancel_timeout_s: float,
    inital_task: asyncio.Task[T] | None = None,
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
    task = inital_task
    async for data in source:
        if task is not None:
            await cancel_task_and_wait(task, cancel_timeout_s)
        task = task_factory(data)
        yield task
