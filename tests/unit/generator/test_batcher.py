# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import copy
import itertools
import random

import pytest

from logprep.generator.batcher import Batcher
from logprep.util.defaults import DEFAULT_BATCH_SIZE


class TestBatcher:

    def setup_method(self):
        self.batches = iter(["/path/to,msg1", "/path/to,msg2", "/path/to,msg3"])

    def test_init(self):
        batcher = Batcher(self.batches)
        assert batcher
        assert isinstance(batcher.event_generator, itertools.cycle)

    def test_init_defaults(self):
        batcher = Batcher(self.batches)
        assert batcher.batch_size is DEFAULT_BATCH_SIZE
        assert isinstance(batcher.rng, random.Random)
        assert batcher.rng.seed() is None

    def test_init_overwrites_defaults(self):
        random_size = random.randint(1, 100000)
        random_seed = random.randint(1, 100000)
        batcher = Batcher(self.batches, **{"batch_size": random_size, "rng": random_seed})
        assert batcher.batch_size is random_size
        assert batcher.rng.random() == random.Random(random_seed).random()

    def test_batcher_iter(self):
        input_events = ["path1,event1", "path2,event2", "path1,event3"]
        batcher = Batcher(input_events, batch_size=2, events=3)
        assert iter(batcher) is batcher
        batches = list(itertools.islice(batcher, 3))
        assert all(isinstance(batch, str) and batch.strip() for batch in batches)

    def test_get_yields_batches_batch_size_even_event_count(self):
        batcher = Batcher(self.batches, batch_size=2, events=2)
        assert next(batcher) == "/path/to,msg1;msg2\n"

    def test_get_yields_batches_batch_size_greater_event_count(self):
        batcher = Batcher(self.batches, batch_size=4, events=2)
        assert next(batcher) == "/path/to,msg1;msg2\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_batch_size_smaller_events(self):
        batcher = Batcher(self.batches, batch_size=1, events=2)
        assert next(batcher) == "/path/to,msg1\n"
        assert next(batcher) == "/path/to,msg2\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_not_enough_examples(self):
        batcher = Batcher(self.batches, batch_size=1, events=4)
        assert next(batcher) == "/path/to,msg1\n"
        assert next(batcher) == "/path/to,msg2\n"
        assert next(batcher) == "/path/to,msg3\n"
        assert next(batcher) == "/path/to,msg1\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_not_enough_examples_bigger_batch_size(self):
        batcher = Batcher(self.batches, batch_size=5, events=4)
        assert next(batcher) == "/path/to,msg1;msg2;msg3;msg1\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_even_batch_size_odd_events(self):
        batcher = Batcher(self.batches, batch_size=2, events=7)
        assert next(batcher) == "/path/to,msg1;msg2\n"
        assert next(batcher) == "/path/to,msg3;msg1\n"
        assert next(batcher) == "/path/to,msg2;msg3\n"
        assert next(batcher) == "/path/to,msg1\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_even_batch_size_even_events(self):
        batcher = Batcher(self.batches, batch_size=4, events=8)
        assert next(batcher) == "/path/to,msg1;msg2;msg3;msg1\n"
        assert next(batcher) == "/path/to,msg2;msg3;msg1;msg2\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_get_yields_batches_by_size1(self):
        batcher = Batcher(self.batches, batch_size=4, events=4)
        assert next(batcher) == "/path/to,msg1;msg2;msg3;msg1\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_raises_value_error_on_negative_batch_size(self):
        batcher = Batcher(self.batches, batch_size=-2)
        with pytest.raises(ValueError):
            next(batcher)

    def test_raises_value_error_on_zero_batch_size(self):
        batcher = Batcher(self.batches, batch_size=0)
        with pytest.raises(ValueError):
            next(batcher)

    def test_batcher_handles_different_paths(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/to,msg3"])
        batcher = Batcher(batches, batch_size=3, events=6)
        assert next(batcher) == "/path/to,msg1;msg3;msg1\n"
        assert next(batcher) == "/path/too,msg2;msg2\n"
        assert next(batcher) == "/path/to,msg3\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_batcher_handles_different_paths_more_events(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/to,msg3"])
        batcher = Batcher(batches, batch_size=3, events=9)
        assert next(batcher) == "/path/to,msg1;msg3;msg1\n"
        assert next(batcher) == "/path/too,msg2;msg2;msg2\n"
        assert next(batcher) == "/path/to,msg3;msg1;msg3\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_batcher_handles_different_paths_more_events_odd_result(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/to,msg3"])
        batcher = Batcher(batches, batch_size=3, events=7)
        assert next(batcher) == "/path/to,msg1;msg3;msg1\n"
        assert next(batcher) == "/path/too,msg2;msg2\n"
        assert next(batcher) == "/path/to,msg3;msg1\n"
        with pytest.raises(StopIteration):
            next(batcher)

    def test_batcher_returns_batches_in_order(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/tooo,msg3"])
        batcher = Batcher(batches, batch_size=2, events=6, shuffle=False)
        assert next(batcher) == "/path/to,msg1;msg1\n"
        assert next(batcher) == "/path/too,msg2;msg2\n"
        assert next(batcher) == "/path/tooo,msg3;msg3\n"

    def test_batcher_shuffles_different_paths(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/tooo,msg3"])
        batcher = Batcher(batches, batch_size=2, events=6, rng=0, shuffle=True)
        assert next(batcher) == "/path/to,msg1;msg1\n"
        assert next(batcher) == "/path/tooo,msg3;msg3\n"
        assert next(batcher) == "/path/too,msg2;msg2\n"

    def test_batcher_shuffles_keeps_event_order(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/to,msg3"])
        batcher = Batcher(batches, batch_size=3, events=9, rng=0, shuffle=True)
        assert next(batcher) == "/path/to,msg1;msg3;msg1\n"
        assert next(batcher) == "/path/to,msg3;msg1;msg3\n"
        assert next(batcher) == "/path/too,msg2;msg2;msg2\n"

    def test_batcher_handles_different_paths_with_shuffle(self):
        batches = iter(["/path/to,msg1", "/path/too,msg2", "/path/tooo,msg3"])
        saved_batches = copy.deepcopy(batches)
        batcher = Batcher(batches, batch_size=3, events=9)
        shuffled_batcher = Batcher(saved_batches, batch_size=3, events=9, shuffle=True, rng=0)
        events = [next(batcher) for _ in range(3)]
        shuffled_events = [next(shuffled_batcher) for _ in range(3)]
        assert events != shuffled_events
