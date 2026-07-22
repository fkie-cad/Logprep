# pylint: disable=missing-docstring
# pylint: disable=protected-access

import asyncio
from collections.abc import Callable
from unittest import mock

import pytest

from logprep.ng.util.retry import (
    _TRANSIENT_FAILURE,
    Backoff,
    BlockingCircuitBreaker,
    RetriesExhaustedError,
    is_exhausted,
)

FAST_BACKOFF = Backoff(initial=0.001, maximum=0.001, jitter=False)


class TransientError(Exception):
    pass


def _breaker(
    max_retries: int | None = None,
    on_transient_failure: Callable[[Exception], None] | None = None,
    concurrency: int = 1,
) -> BlockingCircuitBreaker:
    return BlockingCircuitBreaker(
        backoff=FAST_BACKOFF,
        max_retries=max_retries,
        is_transient=lambda error: isinstance(error, TransientError),
        on_transient_failure=on_transient_failure,
        concurrency=concurrency,
    )


@pytest.mark.timeout(5)
class TestIsExhausted:
    @pytest.mark.parametrize(
        "attempts, max_retries, expected",
        [
            (0, 0, False),
            (1, 0, True),
            (2, 2, False),
            (3, 2, True),
            (1000, None, False),
        ],
    )
    def test_is_exhausted(self, attempts, max_retries, expected):
        assert is_exhausted(attempts, max_retries) is expected


class TestBackoff:
    def test_duration_doubles_per_retry_without_jitter(self):
        backoff = Backoff(initial=2, maximum=600, jitter=False)
        assert [backoff.duration(n) for n in (1, 2, 3)] == [2, 4, 8]

    def test_duration_is_capped_at_maximum(self):
        backoff = Backoff(initial=2, maximum=5, jitter=False)
        assert backoff.duration(100) == 5

    def test_duration_does_not_overflow_for_huge_retry_numbers(self):
        backoff = Backoff(initial=2, maximum=5, jitter=False)
        assert backoff.duration(10_000) == 5

    def test_duration_with_jitter_stays_in_the_upper_half(self):
        backoff = Backoff(initial=4, maximum=600)
        assert all(2 <= backoff.duration(1) <= 4 for _ in range(100))

    async def test_attempts_yields_initial_attempt_plus_retries(self):
        assert [attempt async for attempt in FAST_BACKOFF.attempts(2)] == [1, 2, 3]

    async def test_attempts_with_zero_budget_yields_single_attempt(self):
        assert [attempt async for attempt in FAST_BACKOFF.attempts(0)] == [1]

    async def test_attempts_sleeps_before_every_attempt_but_the_first(self):
        with mock.patch.object(Backoff, "sleep") as mock_sleep:
            assert [_ async for _ in FAST_BACKOFF.attempts(2)] == [1, 2, 3]
        assert mock_sleep.mock_calls == [mock.call(1), mock.call(2)]

    async def test_attempts_with_unlimited_budget_keeps_yielding(self):
        count = 0
        async for attempt in FAST_BACKOFF.attempts(None):
            count += 1
            if attempt == 100:
                break
        assert count == 100


class TestBlockingCircuitBreaker:
    async def test_call_returns_the_send_result(self):
        breaker = _breaker()
        assert await breaker.call(mock.AsyncMock(return_value="response")) == "response"
        assert breaker.healthy

    async def test_call_retries_transient_failures_until_success(self):
        breaker = _breaker()
        send = mock.AsyncMock(side_effect=[TransientError(), TransientError(), "response"])
        assert await breaker.call(send) == "response"
        assert send.await_count == 3
        assert breaker.healthy

    async def test_call_raises_non_transient_failures_without_touching_the_circuit(self):
        breaker = _breaker()
        with pytest.raises(ValueError):
            await breaker.call(mock.AsyncMock(side_effect=ValueError()))
        assert breaker.healthy

    async def test_call_raises_when_the_budget_is_exceeded(self):
        breaker = _breaker(max_retries=1)
        send = mock.AsyncMock(side_effect=TransientError())
        with pytest.raises(RetriesExhaustedError):
            await breaker.call(send)
        assert send.await_count == 2  # initial attempt + 1 retry
        assert not breaker.healthy

    async def test_call_probes_serially_while_the_circuit_is_broken(self):
        breaker = _breaker()
        in_flight, peak_probes = 0, 0

        async def send():
            nonlocal in_flight, peak_probes
            in_flight += 1
            if not breaker.healthy:
                peak_probes = max(peak_probes, in_flight)
            await asyncio.sleep(0.001)
            in_flight -= 1
            if send_mock.await_count <= 5:
                raise TransientError()
            return "response"

        send_mock = mock.AsyncMock(wraps=send)
        results = await asyncio.gather(*(breaker.call(send_mock) for _ in range(3)))
        assert results == ["response"] * 3
        assert peak_probes == 1
        assert breaker.healthy

    async def test_concurrent_failures_of_one_outage_only_open_the_circuit_once(self):
        breaker = _breaker()
        started = asyncio.Barrier(2)

        async def send():
            await started.wait()  # both requests in flight before either fails
            raise TransientError()

        results = await asyncio.gather(
            breaker._attempt(send, probing=False),
            breaker._attempt(send, probing=False),
            return_exceptions=True,
        )
        assert all(result is _TRANSIENT_FAILURE for result in results)
        assert breaker._failures == 1

    async def test_call_limits_concurrent_sends(self):
        breaker = _breaker(concurrency=2)
        in_flight, peak = 0, 0

        async def send():
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.001)
            in_flight -= 1
            return "response"

        results = await asyncio.gather(*(breaker.call(send) for _ in range(5)))
        assert results == ["response"] * 5
        assert peak == 2

    async def test_on_transient_failure_hook_fires_per_recorded_failure(self):
        hook = mock.Mock()
        breaker = _breaker(max_retries=1, on_transient_failure=hook)
        transient = TransientError()
        send = mock.AsyncMock(side_effect=transient)
        with pytest.raises(RetriesExhaustedError):
            await breaker.call(send)
        # fires for every recorded failure, including the exhausting one
        assert hook.mock_calls == [mock.call(transient), mock.call(transient)]

    async def test_on_transient_failure_hook_ignores_non_transient_failures(self):
        hook = mock.Mock()
        breaker = _breaker(on_transient_failure=hook)
        with pytest.raises(ValueError):
            await breaker.call(mock.AsyncMock(side_effect=ValueError()))
        hook.assert_not_called()

    async def test_call_is_cancellable_while_probing(self):
        breaker = _breaker()
        breaker._failures = 1

        async def slow_backoff(*_):
            await asyncio.sleep(10)

        with mock.patch.object(Backoff, "sleep", slow_backoff):
            task = asyncio.create_task(breaker.call(mock.AsyncMock()))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not breaker._limit_to_single_probe.locked()
