"""This module implements queue primitives for multiprocessing usage."""

import logging
import multiprocessing
import sys
import time
from multiprocessing.queues import Queue as BaseQueue
from queue import Empty

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

    def throttle(self, batch_size=1):
        """Throttle put by sleeping."""
        if self.consumed_percent > 90:
            sleep_time = max(
                self.wait_time, int(self.wait_time * self.consumed_percent / batch_size)
            )
            # sleep times in microseconds
            time.sleep(sleep_time / 1000)

    def put(self, obj, block=True, timeout=None, batch_size=1):  # pylint: disable=arguments-differ
        """Put an obj into the queue."""
        self.throttle(batch_size)
        super().put(obj, block=block, timeout=timeout)
