"""Module for caching items and checking if they need to be stored (again)."""

import time
from datetime import timedelta

from collections import OrderedDict
from enum import Enum, auto
from typing import TypeVar, Generic

from attr import define

T = TypeVar("T")


@define
class _CacheEntry(Generic[T]):
    """Entry for cache that consists of value and insertion time"""

    value: T
    insertion_time: float


class NotCached(Enum):
    """Sentinel type for indicating that a key is not cached."""

    NOT_CACHED = auto()


NOT_CACHED = NotCached.NOT_CACHED  # pylint: disable=invalid-name
"""Sentinel value for indicating that a key is not cached."""


class Cache(Generic[T]):
    """Caches items along with a timestamp of when they were last stored."""

    def __init__(
        self,
        max_items: int = 1000000,
        max_timedelta: float = timedelta(days=90).total_seconds(),
    ):
        self._max_items = max_items
        self._max_timedelta = max_timedelta
        self._store = OrderedDict[T]()
        super().__init__()

    def size(self):
        """Return number of cached entries"""
        return len(self._store)

    def clear(self):
        """Remove all entries from the cache"""
        return self._store.clear()

    def get(self, key: str, refresh_lifetime: bool = False) -> T | NotCached:
        """Get cached value from cache if it exists, otherwise return NotCached.NOT_CACHED"""
        entry = self._store.get(key)
        if entry is None:
            return NOT_CACHED
        if time.time() - entry.insertion_time > self._max_timedelta:
            self._store.pop(key)
            return NOT_CACHED
        if refresh_lifetime:
            entry.insertion_time = time.time()
        return entry.value

    def add(self, key: str, value: T):
        """Add the item into the cache or refresh its time to live."""
        if self.refresh_time_to_live(key):
            return

        self._store[key] = _CacheEntry(value, time.time())
        if len(self._store) > self._max_items:
            self._store.popitem(last=False)

    def refresh_time_to_live(self, key) -> bool:
        """Update the items timestamp inside the cache."""
        last_stored = self.get(key)
        if last_stored != NOT_CACHED:
            self._store[key].insertion_time = time.time()
            return True
        return False
