# pylint: disable=missing-docstring
# pylint: disable=protected-access
import datetime
import time
from collections import OrderedDict

import pytest

from logprep.util.cache import Cache


@pytest.fixture(name="cache")
def cache_fixture():
    return Cache(max_items=3, max_timedelta=datetime.timedelta(milliseconds=100))


class TestCache:
    def test_is_ordered_dict(self, cache):
        assert isinstance(cache, OrderedDict)

    def test_init_default(self):
        default_cache = Cache()
        assert default_cache._max_items == 1000000
        assert default_cache._max_timedelta == datetime.timedelta(days=90)

    def test_init_custom(self, cache):
        assert cache._max_items == 3
        assert cache._max_timedelta == datetime.timedelta(milliseconds=100)

    def test_new_cache_is_empty(self, cache):
        assert not cache

    def test_requires_storing_nonzero_deltatime(self, cache):
        for _ in range(3):
            assert cache.requires_storing("foo")
            assert not cache.requires_storing("foo")
            time.sleep(0.1)  # nosemgrep

    def test_requires_storing_zero_deltatime(self, cache):
        cache._max_timedelta = datetime.timedelta(days=0)
        for _ in range(10):
            assert cache.requires_storing("foo")

    def test_max_items(self, cache):
        extra_items = 3
        for i in range(cache._max_items + extra_items):
            assert cache.requires_storing(i)
            assert len(cache) == min(i + 1, cache._max_items)
        assert set(cache.keys()) == set(range(extra_items, cache._max_items + extra_items))
