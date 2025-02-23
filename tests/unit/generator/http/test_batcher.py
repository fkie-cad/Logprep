# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import copy
import itertools
import random

import pytest

from logprep.generator.http.batcher import Batcher
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

    def test_init_overwrites_defaults(self):
        random_size = random.randint(1, 100000)
        batcher = Batcher(self.batches, **{"batch_size": random_size})
        assert batcher.batch_size is random_size

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

    def test_batcher_shuffles_events(self):
        saved_batches = copy.deepcopy(self.batches)
        batcher = Batcher(self.batches, batch_size=1, events=5, shuffle=True)
        shuffled_batcher = Batcher(saved_batches, batch_size=3, events=5, shuffle=True)
        events = [next(batcher) for _ in range(2)]
        shuffled_events = [next(shuffled_batcher) for _ in range(2)]
        assert events != shuffled_events
