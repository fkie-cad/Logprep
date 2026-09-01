"""Module for caching items and checking if they need to be stored (again)."""

import time
from typing import Union

import datetime
from collections import OrderedDict


class Timer:
    """Timer that can be reset."""

    def __init__(self, interval_sec: float):
        self._interval_sec = interval_sec
        self._finished_sec = time.time() + interval_sec

    def reset(self):
        """Reset timer"""
        self._finished_sec = time.time() + self._interval_sec

    def remaining(self):
        """Return seconds until timer is finished"""
        return max(self._finished_sec - time.time(), 0)

    def finished(self):
        """Return if timer is finished"""
        return self.remaining() == 0


class Cache(OrderedDict):
    """Caches items along with a timestamp of when they were last stored."""

    def __init__(
        self, max_items=1000000, max_timedelta=datetime.timedelta(days=90.0), prune_interval=5
    ):
        self._max_items = max_items
        self._max_timedelta = max_timedelta
        self._prune_timer = Timer(prune_interval)
        super().__init__()

    def is_cached(self, item: Union[int, str]) -> bool:
        """Check if the item was stored within the last timedelta.

        Parameters
        ----------
        item : str
            Name of item to check for in the cache.

        """
        last_stored = self.get(item)
        if last_stored is None:
            return False

        if datetime.datetime.now() - last_stored > self._max_timedelta:
            self.pop(item)
            return False
        return True

    def add(self, item: Union[int, str]):
        """Add the item into the cache or update its timestamp.

        Parameters
        ----------
        item : str
            Item to add into the cache.

        """
        if self.update_cache(item):
            return

        self[item] = datetime.datetime.now()
        if len(self) > self._max_items:
            self.popitem(last=False)

    def update_cache(self, item: int | str) -> bool:
        """Update the items timestamp inside the cache.

        Parameters
        ----------
        item : str
            Item whose timestamp to update in the cache.

        """
        last_stored = self.get(item)
        if last_stored is not None:
            self[item] = datetime.datetime.now()
            return True
        return False

    def prune_decayed(self):
        """Prune cache if timer is finished."""
        if self._prune_timer.finished():
            now = datetime.datetime.now()
            to_prune = [key for key, added in self.items() if now - added > self._max_timedelta]
            for item in to_prune:
                if item in self:
                    del self[item]
            self._prune_timer.reset()
