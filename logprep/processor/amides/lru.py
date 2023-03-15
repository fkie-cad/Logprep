""" This module contains a simple LRU-Cache implementation which keeps track
of recently used objects and their reference-keys.
"""
from collections import OrderedDict


class LRUCache:
    """Simple LRUCache implementation to keep track of recently used items."""

    def __init__(self, max_items=1000000):
        """Inits LRUCache objects."""
        self._dict = OrderedDict()
        self._max_items = max_items

    def relative_load(self):
        """Return the current relative cache load.

        Returns
        -------
        cache_load: float
            The current cache load.
        """
        return self.num_entries() / self._max_items

    def num_entries(self):
        """Returns the absolute number of cache entries."""
        return len(self._dict)

    def insert(self, key: str, value: object):
        """Insert key-value-item into the cache.

        Parameters
        ----------
        key: str
            The reference key.
        value: object
            Arbitrary object to be stored.
        """
        self._dict[key] = value
        self._dict.move_to_end(key, last=False)
        if len(self._dict) > self._max_items:
            self._dict.popitem()

    def get(self, key: str, default: object = None):
        """Get element from cache referenced by key. In case of cache miss,
        return optional default-object.

        Parameters
        ----------
        key: str
            Key of the value which should be returned.
        default: object
            Default value which should be returned in case of a cache miss.

        Returns
        -------
        : object
            Object that is referenced by the given key.
        """
        if key not in self._dict:
            return default

        self._dict.move_to_end(key, last=False)
        return self._dict[key]

    def items(self):
        """Return all cached values and their corresponding keys.

        Returns
        -------
        :dict_items
            Iterator of key and value items.
        """
        return self._dict.items()
