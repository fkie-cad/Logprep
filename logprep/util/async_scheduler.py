"""Async wrappers for schedule.Job and schedule.Scheduler."""

import asyncio
import datetime
import inspect
from collections.abc import Hashable
from typing import Any

from schedule import CancelJob, Job, Scheduler


class AsyncJob(Job):
    """A scheduled job supporting synchronous and asynchronous callables."""

    async def run(self) -> Any:
        """Run the job and await asynchronous results."""
        if self._is_overdue(datetime.datetime.now()):
            return CancelJob

        if self.job_func is None:
            raise RuntimeError("Job has no function configured")

        ret = self.job_func()

        if inspect.isawaitable(ret):
            ret = await ret

        self.last_run = datetime.datetime.now()
        self._schedule_next_run()

        assert self.next_run is not None

        if self._is_overdue(self.next_run):
            return CancelJob

        return ret


class AsyncScheduler:
    """Scheduler supporting synchronous and asynchronous jobs."""

    def __init__(self) -> None:
        self._scheduler = Scheduler()

    @property
    def jobs(self) -> list[Job]:
        """Return all scheduled jobs."""
        return self._scheduler.jobs

    def every(self, interval: int = 1) -> AsyncJob:
        """Create a new asynchronous job."""
        return AsyncJob(interval, self)  # type: ignore[arg-type]

    def get_jobs(self, tag: Hashable | None = None) -> list[Job]:
        """Return scheduled jobs, optionally filtered by tag."""
        return self._scheduler.get_jobs(tag)

    def clear(self, tag: Hashable | None = None) -> None:
        """Remove scheduled jobs, optionally filtered by tag."""
        self._scheduler.clear(tag)

    def cancel_job(self, job: Job) -> None:
        """Cancel a scheduled job."""
        self._scheduler.cancel_job(job)

    def get_next_run(self, tag: Hashable | None = None) -> datetime.datetime | None:
        """Return the next scheduled run."""
        return self._scheduler.get_next_run(tag)

    @property
    def next_run(self) -> datetime.datetime | None:
        """Return the next scheduled run."""
        return self._scheduler.next_run

    @property
    def idle_seconds(self) -> float | None:
        """Return the number of seconds until the next scheduled run."""
        return self._scheduler.idle_seconds

    async def _run_job(self, job: Job) -> None:
        ret = job.run()

        if inspect.isawaitable(ret):
            ret = await ret

        if isinstance(ret, CancelJob) or ret is CancelJob:
            self.cancel_job(job)

    async def run_pending(self) -> None:
        """Run all jobs that are currently due."""
        runnable_jobs = (job for job in self.jobs if job.should_run)

        for job in sorted(runnable_jobs):
            await self._run_job(job)

    async def run_all(self, delay_seconds: int = 0) -> None:
        """Run all jobs regardless of their scheduled run time."""
        for job in self.jobs[:]:
            await self._run_job(job)

            if delay_seconds:
                await asyncio.sleep(delay_seconds)
