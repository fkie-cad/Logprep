# pylint: disable=unused-variable
import pytest

from logprep.processor.amides.lru import LRUCache

pytest.importorskip("logprep.processor.amides")


class TestLRUCache:
    def test_set_item(self):
        expected_last = ("some_rule", 0)
        expected_first = ("another_rule", 1)
        expected_middle = ("other_rule", 0)

        lru = LRUCache(max_items=3)
        lru.insert("some_rule", 0)
        lru.insert("other_rule", 0)
        lru.insert("another_rule", 1)

        assert list(lru.items()) == [expected_first, expected_middle, expected_last]

    def test_set_item_which_already_exists(self):
        first_item = ("some_rule", 0)
        second_item = ("another_rule", 1)
        third_item = ("some_rule", 1)

        lru = LRUCache(max_items=3)
        lru.insert("some_rule", 0)
        lru.insert("another_rule", 1)
        lru.insert("some_rule", 1)

        assert list(lru.items()) == [third_item, second_item]

    def test_set_item_when_cache_is_full(self):
        first_item = ("some_rule", 0)
        second_item = ("another_rule", 1)
        third_item = ("other_rule", 0)

        lru = LRUCache(max_items=2)
        lru.insert("some_rule", 0)
        lru.insert("another_rule", 1)
        lru.insert("other_rule", 0)

        assert list(lru.items()) == [third_item, second_item]

    def test_get_item(self):
        lru = LRUCache(max_items=3)
        lru.insert("some_rule", 0)

        assert lru.get("some_rule") == 0

    def test_get_item_missing_key_return_default(self):
        lru = LRUCache()
        assert not lru.get("some_rule")

    def test_determine_cache_load(self):
        lru = LRUCache(max_items=4)
        lru.insert("some_rule", 0)
        assert lru.relative_load() == 0.25
        assert lru.num_entries() == 1
        lru.insert("other_rule", 1)
        assert lru.relative_load() == 0.5
        assert lru.num_entries() == 2
        lru.insert("another_rule", 0)
        assert lru.relative_load() == 0.75
