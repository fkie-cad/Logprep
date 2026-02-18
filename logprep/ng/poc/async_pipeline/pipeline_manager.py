"""
Pipeline orchestration and lifecycle management.

This module provides the coordinator responsible for running a validated, linear
worker chain and for managing long-lived background tasks bound to the manager
lifecycle. It implements dynamic handler resolution for pipeline-bound workers
and supports controlled restarts via soft shutdown and reload semantics.

The focus is operational correctness: predictable startup/shutdown behavior,
reload safety, and fail-fast propagation of task failures via a single manager
lifetime signal.
"""

import asyncio
import inspect
from asyncio import AbstractEventLoop
from collections.abc import Callable, Coroutine
from traceback import print_tb
from types import FunctionType
from typing import Any, Concatenate, ParamSpec, TypeAlias, TypeVar, cast

from async_pipeline.types import Handler, HandlerResolver
from async_pipeline.utils.worker_chain_validator import (
    validate_and_sort_linear_worker_chain,
)
from async_pipeline.worker.pipeline_worker import PipelineWorker

P = ParamSpec("P")
SelfT = TypeVar("SelfT")

AsyncMarked: TypeAlias = Callable[Concatenate[SelfT, P], Coroutine[Any, Any, Any]]
BackgroundTaskFactory: TypeAlias = Callable[[], Coroutine[Any, Any, Any]]


def background_task(func: AsyncMarked[SelfT, P]) -> AsyncMarked[SelfT, P]:
    """
    Mark an async function or method as a pipeline background task.

    The decorator does not alter runtime behavior. It only attaches
    metadata used by PipelineManager during background task discovery.

    Marked callables are automatically registered and executed as
    long-lived control-plane tasks bound to the manager lifecycle.

    Notes
    -----
    - Only async callables are supported.
    - The decorator performs no wrapping or scheduling.
    - Execution semantics are defined entirely by PipelineManager.
    """

    setattr(func, "__background_task__", True)
    return func


class PipelineManager(HandlerResolver):
    """
    Orchestrates a linear chain of PipelineWorker instances and manager-scoped background tasks.

    The manager binds itself as a HandlerResolver for PipelineWorkers, starts/stops worker tasks,
    and optionally discovers and runs @background_task-marked async methods.

    Lifecycle:
    - run(): start workers + background tasks and wait until stop_event is set
    - soft_shut_down(): stop worker tasks only (manager stays alive)
    - reload(): soft shutdown + restart workers (background tasks keep running)
    - shut_down(): stop workers + background tasks and end manager lifetime
    """

    def __init__(
        self,
        workers: list[PipelineWorker[Any]],
        loop: AbstractEventLoop | None = None,
    ) -> None:
        """
        Initialize the manager with a worker chain and optional event loop.

        Workers are validated/sorted into a strict linear chain and PipelineWorkers are
        bound to this manager as their handler resolver.
        """
        self._loop: AbstractEventLoop | None = loop
        self._workers: list[PipelineWorker[Any]] = self._validate_and_bind_workers(workers=workers)

        # public: background tasks and subclasses may rely on this as the manager lifetime signal
        self.stop_event = asyncio.Event()

        self._worker_tasks: set[asyncio.Task[Any]] = set()
        self._background_tasks: set[asyncio.Task[Any]] = set()

        self._registered_background_task_factories: set[BackgroundTaskFactory] = set()
        self._background_tasks_started = False

        self._exceptions: list[BaseException] = []
        self._reload_lock = asyncio.Lock()

    def _validate_and_bind_workers(
        self,
        workers: list[PipelineWorker[Any]],
    ) -> list[PipelineWorker[Any]]:
        """
        Validate worker wiring and bind this manager as their handler resolver.

        Ensures the worker chain forms a strict linear pipeline and resets
        resolver bindings to keep handler resolution consistent.
        """

        workers = validate_and_sort_linear_worker_chain(workers)

        for worker in workers:
            if isinstance(worker, PipelineWorker):
                worker.bind_resolver(self)

        return workers

    def resolve(self, name: str) -> Handler[Any]:
        """
        Resolve a handler by name on this manager instance.

        Implementations typically provide handler methods on subclasses which are looked up
        dynamically by attribute name.
        """
        handler = getattr(self, name, None)
        if handler is None or not callable(handler):
            raise AttributeError(f"Missing handler {name!r} on {type(self).__name__}.")
        return cast(Handler[Any], handler)

    def register_additional_background_tasks(self, callback: BackgroundTaskFactory) -> None:
        """
        Register an additional manager-scoped background task factory.

        The callback must be an async callable producing a coroutine and will be scheduled
        when start_background_tasks() runs.
        """
        if not inspect.iscoroutinefunction(callback):
            raise TypeError(
                "register_additional_background_tasks() only accepts async callables "
                "(async def ...). Sync callables are not supported."
            )
        self._registered_background_task_factories.add(callback)

    def _setup(self) -> None:
        """Perform manager initialization steps that require a fully constructed instance."""
        self._auto_register_marked_background_tasks()

    def start_background_tasks(self) -> None:
        """
        Start manager-scoped background tasks once per manager lifetime.

        This is intended for long-lived control-plane tasks (metrics, cleanup, etc.).
        """
        if self._background_tasks_started:
            return
        if self._loop is None:
            raise RuntimeError("start_background_tasks() requires an event loop.")

        self._background_tasks_started = True
        self._enqueue_registered_background_tasks()

    def _auto_register_marked_background_tasks(self) -> None:
        """
        Discover and register @background_task-marked async methods.

        Discovery inspects the class hierarchy without invoking attribute access on the
        instance to avoid side effects from descriptors/properties.
        """
        seen: set[str] = set()

        for cls in type(self).mro():
            if cls is object:
                break

            for name, attr in cls.__dict__.items():
                if name in seen:
                    continue
                seen.add(name)

                func: Callable[..., Any] | None = None
                if isinstance(attr, staticmethod):
                    func = cast(Callable[..., Any], attr.__func__)
                elif isinstance(attr, classmethod):
                    func = cast(Callable[..., Any], attr.__func__)
                elif isinstance(attr, FunctionType):
                    func = attr

                if func is None:
                    continue

                if getattr(func, "__background_task__", False):
                    bound = getattr(self, name)

                    if not inspect.iscoroutinefunction(bound):
                        raise TypeError(
                            f"Background task {type(self).__name__}.{name} is marked with "
                            "@background_task but is not async. Only async background tasks are supported."
                        )

                    self._registered_background_task_factories.add(
                        cast(BackgroundTaskFactory, bound)
                    )

    def _enqueue_registered_background_tasks(self) -> None:
        """Schedule all registered background task factories on the configured event loop."""
        if self._loop is None:
            raise RuntimeError("_enqueue_registered_background_tasks() requires an event loop.")

        for callback in self._registered_background_task_factories:
            task = self._loop.create_task(callback())
            self._add_background_task(task)

    def run_workers(self) -> None:
        """
        Start worker tasks (data-plane).

        Worker tasks may be restarted on reload; background tasks are not.
        """
        if self._loop is None:
            raise RuntimeError("run_workers() requires an event loop.")

        for worker in self._workers:
            t = self._loop.create_task(worker.run())
            self._add_worker_task(t)

    async def run(self) -> None:
        """
        Run the manager until stop_event is set.

        Starts workers and background tasks and then blocks waiting for shutdown.
        """
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        self._setup()
        self.run_workers()
        self.start_background_tasks()

        await self.stop_event.wait()

    async def reload(self) -> None:
        """
        Restart worker tasks while keeping the manager alive.

        Performs a soft shutdown (workers only), re-binds PipelineWorkers to this resolver,
        and starts workers again. Background tasks continue running.
        """

        async with self._reload_lock:
            print("Reloading...")
            await self.soft_shut_down()
            self._workers = self._validate_and_bind_workers(workers=self._workers)
            self.run_workers()
            print("Reload done.")

    async def soft_shut_down(self) -> None:
        """
        Stop worker tasks without ending the manager lifetime.

        Intended to allow reload/restart of the data-plane while keeping control-plane
        background tasks running.
        """
        await self._shut_down_workers()

    async def shut_down(self) -> None:
        """
        Fully shut down the manager.

        Stops workers and background tasks, clears registrations, and signals stop_event
        so run() can exit.
        """
        await self.soft_shut_down()
        await self._shut_down_background_tasks()

        self._registered_background_task_factories.clear()
        self.stop_event.set()

    async def _shut_down_workers(self) -> None:
        """Signal, cancel, and await completion of all worker tasks."""
        for worker in self._workers:
            worker.stop_event.set()

        current = asyncio.current_task()
        tasks = [t for t in self._worker_tasks if t is not current]

        for t in tasks:
            t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        self._worker_tasks.clear()

        for worker in self._workers:
            worker.stop_event = asyncio.Event()

    async def _shut_down_background_tasks(self) -> None:
        """Cancel and await completion of all manager-scoped background tasks."""
        current = asyncio.current_task()
        tasks = [t for t in self._background_tasks if t is not current]

        for t in tasks:
            t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()

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
                self.stop_event.set()

        task.add_done_callback(_done)

    def _add_background_task(self, task: asyncio.Task[Any]) -> None:
        """Track a background task and fail-fast on exceptions."""
        self._background_tasks.add(task)

        def _done(t: asyncio.Task[Any]) -> None:
            self._background_tasks.discard(t)

            if t.cancelled():
                return

            exc = t.exception()
            if exc is not None:
                self._exceptions.append(exc)
                self.stop_event.set()

        task.add_done_callback(_done)
