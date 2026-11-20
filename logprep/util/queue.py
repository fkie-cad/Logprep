"""This module implements queue primitives for multiprocessing usage."""

import asyncio
import logging
import multiprocessing
import sys
import time
from multiprocessing.queues import Queue as BaseQueue
from queue import Empty, Full

logger = logging.getLogger("Queue")


class _QueueWithSize(BaseQueue):
    """
    Queue with extra counter to fix `qsize` and `empty` on MacOS.
    """

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
            self.__size = multiprocessing.Value("i", 0)
        except OSError as error:
            if error.errno == 22 and "maxsize" in kwargs:
                raise ValueError(
                    "Invalid argument. "
                    "Parameter `maxsize` might exceed upper boundary for queue implementation."
                ) from error
            raise

    def put(self, *args, **kwargs):
        super().put(*args, **kwargs)
        with self.__size.get_lock():
            self.__size.value += 1

    def get(self, *args, **kwargs):
        try:
            value = super().get(*args, **kwargs)
        except Empty:
            return None
        with self.__size.get_lock():
            self.__size.value -= 1
        return value

    def qsize(self):
        return self.__size.value


Queue: type[BaseQueue] = _QueueWithSize if sys.platform == "darwin" else BaseQueue
"""A queue type which provides `qsize` and works on all relevant platforms"""


class ThrottlingQueue(Queue):  # type: ignore
    """A queue that throttles puts when coming close to reaching capacity"""

    wait_time = 5

    @property
    def consumed_percent(self) -> int:
        """Return the percentage of items consumed."""
        return int((self.qsize() / self.capacity) * 100)

    def __init__(self, ctx, maxsize):
        super().__init__(ctx=ctx, maxsize=maxsize)
        self.capacity = maxsize
        self.call_time = None

    def throttle_time(self, batch_size=1) -> float:
        """Seconds a put of :code:`batch_size` objs should wait, 0 below 90% usage."""
        if self.consumed_percent <= 90:
            return 0.0
        sleep_ms = max(self.wait_time, int(self.wait_time * self.consumed_percent / batch_size))
        return sleep_ms / 1000

    def throttle(self, batch_size=1):
        """Throttle put by sleeping."""
        if sleep_time := self.throttle_time(batch_size):
            time.sleep(sleep_time)

    def put(self, obj, block=True, timeout=None, batch_size=1):  # pylint: disable=arguments-differ
        """Put an obj into the queue."""
        self.throttle(batch_size)
        super().put(obj, block=block, timeout=timeout)

    async def put_batch(self, objs: list) -> None:
        """Put all objs or none of them. Raises :code:`queue.Full` if they don't fit.

        Throttles without blocking the event loop. Atomic for a single producer event loop,
        as nothing is awaited between the capacity check and the puts.
        """
        await asyncio.sleep(self.throttle_time(len(objs)))
        if self.qsize() + len(objs) > self.capacity:
            raise Full
        for obj in objs:
            super().put(obj, block=False)
