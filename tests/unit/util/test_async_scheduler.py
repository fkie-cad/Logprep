"""Tests for the asynchronous scheduler"""

import datetime
from unittest import mock

from schedule import CancelJob

from logprep.util.async_scheduler import AsyncScheduler


async def test_runs_async_job():
    scheduler = AsyncScheduler()
    callback = mock.AsyncMock()

    scheduler.every(1).seconds.do(callback)

    await scheduler.run_all()

    callback.assert_awaited_once()


async def test_runs_sync_job():
    scheduler = AsyncScheduler()
    callback = mock.Mock()

    scheduler.every(1).seconds.do(callback)

    await scheduler.run_all()

    callback.assert_called_once()


async def test_run_pending_runs_only_due_jobs():
    scheduler = AsyncScheduler()
    callback = mock.AsyncMock()

    job = scheduler.every(10).seconds.do(callback)

    await scheduler.run_pending()
    callback.assert_not_awaited()

    # Make the job due without waiting for the interval.
    job.next_run = datetime.datetime.now() - datetime.timedelta(seconds=1)

    await scheduler.run_pending()
    callback.assert_awaited_once()


def test_async_job_references_async_scheduler():
    scheduler = AsyncScheduler()

    job = scheduler.every(1).seconds.do(mock.AsyncMock())

    assert job.scheduler is scheduler


async def test_cancel_job_removes_job():
    scheduler = AsyncScheduler()
    callback = mock.AsyncMock(return_value=CancelJob)

    job = scheduler.every(1).seconds.do(callback)

    await scheduler.run_all()

    callback.assert_awaited_once()
    assert job not in scheduler.jobs


async def test_run_reschedules_job():
    scheduler = AsyncScheduler()
    callback = mock.AsyncMock()

    job = scheduler.every(1).seconds.do(callback)
    previous_next_run = job.next_run

    await scheduler.run_all()

    assert job.last_run is not None
    assert job.next_run is not None
    assert previous_next_run is not None
    assert job.next_run > previous_next_run
