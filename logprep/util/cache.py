"""Module for caching items and checking if they need to be stored (again)."""

from typing import Union

import datetime
from collections import OrderedDict


class Cache(OrderedDict):
    """Caches items along with a timestamp of when they were last stored."""

    EPOCH = datetime.datetime(1970, 1, 1)

    def __init__(self, max_items=1000000, max_timedelta=datetime.timedelta(days=90.0)):
        self._max_items = max_items
        self._max_timedelta = max_timedelta
        super().__init__()

    def requires_storing(self, item: Union[int, str]) -> bool:
        """Check if the item was stored within the last timedelta.

        Parameters
        ----------
        item : str
            Name of item to check for in the cache.

        """
        now = datetime.datetime.now()
        last_stored = self.get(item, self.__class__.EPOCH)
        self[item] = last_stored
        self.move_to_end(item)
        if self._max_timedelta.total_seconds() == 0.0 or now - last_stored > self._max_timedelta:
            self[item] = now
            if len(self) > self._max_items:
                self.popitem(last=False)
            return True
        return False
