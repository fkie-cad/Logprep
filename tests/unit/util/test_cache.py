# pylint: disable=missing-docstring
# pylint: disable=protected-access
import datetime
import time
from collections import OrderedDict

import pytest

from logprep.util.cache import Cache, Timer


@pytest.fixture(name="cache")
def cache_fixture():
    return Cache(
        max_items=3, max_timedelta=datetime.timedelta(milliseconds=100), prune_interval=0.1
    )


class TestTimer:
    def test_reset_timer(self):
        timer = Timer(60)
        start_remaining = timer.remaining()
        time.sleep(0.01)  # nosemgrep
        assert timer.remaining() < start_remaining
        pre_reset = timer.remaining()
        time.sleep(0.01)  # nosemgrep
        timer.reset()
        assert timer.remaining() > pre_reset

    def test_finished(self):
        timer = Timer(0.1)
        time.sleep(0.01)  # nosemgrep
        assert not timer.finished()
        time.sleep(0.1)  # nosemgrep
        assert timer.finished()


class TestCache:
    def test_is_ordered_dict(self, cache: Cache):
        assert isinstance(cache, OrderedDict)

    def test_init_default(self):
        default_cache = Cache()
        assert default_cache._max_items == 1000000
        assert default_cache._max_timedelta == datetime.timedelta(days=90)

    def test_init_custom(self, cache: Cache):
        assert cache._max_items == 3
        assert cache._max_timedelta == datetime.timedelta(milliseconds=100)

    def test_new_cache_is_empty(self, cache: Cache):
        assert not cache

    def test_is_cached_nonzero_deltatime(self, cache: Cache):
        for _ in range(3):
            assert not cache.is_cached("foo")
            cache.add("foo")
            assert cache.is_cached("foo")
            time.sleep(0.1)  # nosemgrep

    def test_is_cached_zero_deltatime(self, cache: Cache):
        cache._max_timedelta = datetime.timedelta(days=0)
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

    def test_prune_decayed(self, cache: Cache):
        for idx in range(3):
            cache.add(idx)
            cache.prune_decayed()
            assert idx in cache
            time.sleep(cache._prune_timer.remaining() + 0.005)  # nosemgrep
            assert idx in cache
            cache.prune_decayed()
            assert idx not in cache

    def test_prune_decayed_and_keep_rest(self, cache: Cache):
        cache.add(0)
        time.sleep(0.15)
        cache.add(1)
        cache.add(2)
        assert len(cache) == 3
        cache.prune_decayed()
        assert len(cache) == 2

    def test_add_refreshes(self, cache: Cache):
        assert not cache.is_cached("foo")
        cache.add("foo")
        assert cache.is_cached("foo")
        old_decay_time = cache.get("foo")
        time.sleep(0.1)
        new_decay = cache.add("foo")
        assert new_decay is not None
        assert old_decay_time is not None
        assert new_decay > old_decay_time
