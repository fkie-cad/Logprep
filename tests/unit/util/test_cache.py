# pylint: disable=missing-docstring
# pylint: disable=protected-access
import time
from collections import OrderedDict
from datetime import timedelta

import pytest

from logprep.util.cache import Cache


@pytest.fixture(name="cache")
def cache_fixture():
    return Cache(max_items=3, max_timedelta=0.1)


class TestCache:
    def test_is_ordered_dict(self, cache: Cache):
        assert isinstance(cache, OrderedDict)

    def test_init_default(self):
        default_cache = Cache()
        assert default_cache._max_items == 1000000
        assert default_cache._max_timedelta == timedelta(days=90).total_seconds()

    def test_init_custom(self, cache: Cache):
        assert cache._max_items == 3
        assert cache._max_timedelta == 0.1

    def test_new_cache_is_empty(self, cache: Cache):
        assert not cache

    def test_is_cached_nonzero_deltatime(self, cache: Cache):
        for _ in range(3):
            assert not cache.is_cached("foo")
            cache.add("foo")
            assert cache.is_cached("foo")
            time.sleep(0.1)  # nosemgrep

    def test_is_cached_zero_deltatime(self, cache: Cache):
        cache._max_timedelta = 0
        for _ in range(10):
            assert not cache.is_cached("foo")

    def test_max_items_add(self, cache):
        extra_items = 3
        cache_hash = hash(frozenset(cache))
        for i in range(cache._max_items + extra_items):
            cache.add(i)
            new_cache_hash = hash(frozenset(cache))
            assert cache_hash != new_cache_hash
            cache_hash = new_cache_hash
            assert len(cache) == min(i + 1, cache._max_items)
        assert set(cache.keys()) == set(range(extra_items, cache._max_items + extra_items))

    def test_add_refreshes(self, cache: Cache):
        assert not cache.is_cached("foo")
        cache.add("foo")
        assert cache.is_cached("foo")
        old_decay_time = cache.get("foo").insertion_time
        time.sleep(0.1)
        cache.add("foo")
        new_decay = cache.get("foo").insertion_time
        assert new_decay is not None
        assert old_decay_time is not None
        assert new_decay > old_decay_time
