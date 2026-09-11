"""Module for caching items and checking if they need to be stored (again)."""

import time
from dataclasses import dataclass
from datetime import timedelta

from collections import OrderedDict
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    insertion_time: float


class Cache(OrderedDict):
    """Caches items along with a timestamp of when they were last stored."""

    def __init__(
        self,
        max_items=1000000,
        max_timedelta=timedelta(days=90).total_seconds(),
    ):
        self._max_items = max_items
        self._max_timedelta = max_timedelta
        super().__init__()

    def __getitem__(self, key) -> CacheEntry:
        return super().__getitem__(key)

    def get(self, *args, **kwargs) -> CacheEntry | None:
        """Get a cached item with the type CacheEntry."""
        return super().get(*args, **kwargs)

    def is_cached(self, key: str) -> bool:
        """Check if the item has exceeded its time to live.

        Parameters
        ----------
        key : str
            Name of item to check for in the cache.

        """
        last_stored = self.get(key)
        if last_stored is None:
            return False

        if time.time() - last_stored.insertion_time > self._max_timedelta:
            self.pop(key)
            return False
        return True

    def add(self, key: str, value: Any = None):
        """Add the item into the cache or refresh its time to live.

        Parameters
        ----------
        key : str
            Key for item to add into the cache.
        value : Any
            Value of item to add into the cache.

        """
        if self.refresh_time_to_live(key):
            return

        self[key] = CacheEntry(value, time.time())
        if len(self) > self._max_items:
            self.popitem(last=False)

    def refresh_time_to_live(self, key) -> bool:
        """Update the items timestamp inside the cache.

        Parameters
        ----------
        key : str
            Item whose timestamp to update in the cache.

        """
        last_stored = self.get(key)
        if last_stored is not None:
            self[key].insertion_time = time.time()
            return True
        return False
