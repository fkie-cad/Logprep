"""Async wrappers for schedule.Job and schedule.Scheduler."""

import asyncio
import datetime
import inspect
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

        if self._is_overdue(self.next_run):
            return CancelJob

        return ret


class AsyncScheduler(Scheduler):
    """Scheduler supporting synchronous and asynchronous jobs."""

    def every(self, interval: int = 1) -> AsyncJob:
        return AsyncJob(interval, self)

    async def _run_job(self, job: AsyncJob) -> None:
        ret = await job.run()

        if isinstance(ret, CancelJob) or ret is CancelJob:
            self.cancel_job(job)

    async def run_pending(self) -> None:
        runnable_jobs = (job for job in self.jobs if job.should_run)

        for job in sorted(runnable_jobs):
            await self._run_job(job)

    async def run_all(self, delay_seconds: int = 0) -> None:
        for job in self.jobs[:]:
            await self._run_job(job)

            if delay_seconds:
                await asyncio.sleep(delay_seconds)
