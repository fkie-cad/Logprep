"""
Retry helpers
=============

Shared retry and connection management helpers.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from enum import Enum, auto
from typing import TypeVar

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException

T = TypeVar("T")


class _TransientFailure(Enum):
    """Internal sentinel: the attempt failed transiently and was recorded."""

    TRANSIENT_FAILURE = auto()


_TRANSIENT_FAILURE = _TransientFailure.TRANSIENT_FAILURE  # pylint: disable=invalid-name
"""Internal sentinel: the attempt failed transiently and was recorded."""


class RetriesExhaustedError(LogprepException):
    """Indicates that all retry attempts failed"""


def is_exhausted(attempts: int, max_retries: int | None) -> bool:
    """Whether a retries (:code:`None` = unlimited) are exhausted after :code:`attempts` failures"""
    return max_retries is not None and attempts > max_retries


@define(kw_only=True, frozen=True)
class Backoff:
    """Capped exponential backoff with equal jitter."""

    initial: float = field(
        default=2.0,
        validator=[validators.instance_of((int, float)), validators.gt(0)],
    )
    """Backoff before the first retry in seconds; doubles per retry."""

    maximum: float = field(
        default=600.0,
        validator=[validators.instance_of((int, float)), validators.gt(0)],
    )
    """Upper bound for the backoff in seconds."""

    jitter: bool = field(default=True, validator=validators.instance_of(bool))
    """Randomizes the upper half of each backoff duration."""

    def duration(self, retry_number: int) -> float:
        """Backoff in seconds before retry :code:`retry_number` (1-based)."""
        exponent = min(retry_number - 1, 64)  # clamped: avoids float overflow, exceeds any maximum
        duration = min(self.maximum, self.initial * 2**exponent)
        if self.jitter:
            return duration / 2 + random.uniform(0, duration / 2)
        return duration

    async def sleep(self, retry_number: int) -> None:
        """Sleeps the (cancellable) backoff duration for the given retry."""
        await asyncio.sleep(self.duration(retry_number))

    async def attempts(self, max_retries: int | None) -> AsyncIterator[int]:
        """Yields attempt numbers (1-based), sleeping before every attempt
        but the first, until the retry budget is exhausted."""
        attempt = 0
        while not is_exhausted(attempt, max_retries):
            if attempt:  # failed attempts so far == retry number of the next one
                await self.sleep(attempt)
            attempt += 1
            yield attempt


@define(kw_only=True)
class BlockingCircuitBreaker:
    """
    A circuit breaker that blocks instead of failing fast.

    While the circuit is broken, one caller at a time probes it after the shared, growing backoff;
    all others queue on the probe lock. Beyond :code:`max_retries` consecutive failures,
    each further failed probe raises :code:`RetriesExhaustedError` to its caller,
    so work keeps draining during a long outage. Any success closes the circuit.
    """

    _backoff: Backoff = field(validator=validators.instance_of(Backoff))
    _max_retries: int | None = field(
        default=None,
        validator=validators.optional([validators.instance_of(int), validators.ge(0)]),
    )
    _is_transient: Callable[[Exception], bool] = field(validator=validators.is_callable())
    """Whether an exception is considered circuit breaking; others pass through"""

    _on_transient_failure: Callable[[Exception], None] | None = field(
        default=None, validator=validators.optional(validators.is_callable())
    )
    """Optional hook invoked for every recorded transient failure, e.g. to feed metrics."""

    _concurrency: int = field(default=1, validator=[validators.instance_of(int), validators.ge(1)])
    """Maximum number of sends allowed concurrently"""

    _failures: int = field(default=0, init=False)
    """Consecutive transient failures; 0 means healthy."""

    _limit_to_single_probe: asyncio.Lock = field(factory=asyncio.Lock, init=False, repr=False)
    _limit_concurrent_send: asyncio.Semaphore = field(init=False, repr=False)

    def __attrs_post_init__(self):
        self._limit_concurrent_send = asyncio.Semaphore(self._concurrency)

    @property
    def healthy(self) -> bool:
        """Whether the last send through this breaker succeeded."""
        return self._failures == 0

    async def call(self, send: Callable[[], Awaitable[T]]) -> T:
        """Awaits :code:`send()` until it succeeds, retrying transient
        failures; non-transient exceptions propagate untouched."""
        while True:
            if not self.healthy:
                async with self._limit_to_single_probe:
                    if not self.healthy:  # might have recovered during the wait
                        await self._backoff.sleep(self._failures)
                        async with self._limit_concurrent_send:
                            result = await self._attempt(send, probing=True)
                        if result is not _TRANSIENT_FAILURE:
                            return result
                        continue
                    # circuit closed while we waited: send concurrently below
            async with self._limit_concurrent_send:
                if not self.healthy:  # might have failed during the wait
                    continue
                result = await self._attempt(send, probing=False)
            if result is not _TRANSIENT_FAILURE:
                return result

    async def _attempt(
        self, send: Callable[[], Awaitable[T]], probing: bool
    ) -> T | _TransientFailure:
        """Runs one attempt and records its outcome. Returns the result, or
        :code:`_TRANSIENT_FAILURE` for a recorded transient failure."""
        try:
            result = await send()
        except Exception as error:
            if not self._is_transient(error):
                raise
            # probe failures accumulate, non-probes only activate failure mode
            self._failures = self._failures + 1 if probing else max(self._failures, 1)
            if self._on_transient_failure is not None:
                self._on_transient_failure(error)
            if is_exhausted(self._failures, self._max_retries):
                raise RetriesExhaustedError(
                    f"connection retries exhausted after {self._failures} consecutive failures"
                ) from error
            return _TRANSIENT_FAILURE
        self._failures = 0
        return result
