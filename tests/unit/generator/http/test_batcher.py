# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import random

import pytest

from logprep.generator.http.batcher import Batcher
from logprep.util.defaults import DEFAULT_BATCH_SIZE


class TestBatcher:

    def setup_method(self):
        self.batches = iter(["msg1", "msg2", "msg3"])

    def test_init(self):
        batcher = Batcher(self.batches)
        assert batcher
        assert batcher.events is self.batches

    def test_init_defaults(self):
        batcher = Batcher(self.batches)
        assert batcher.batch_size is DEFAULT_BATCH_SIZE

    def test_init_overwrites_defaults(self):
        random_size = random.randint(1, 100000)
        batcher = Batcher(self.batches, **{"batch_size": random_size})
        assert batcher.batch_size is random_size

    def test_get_yields_batches(self):
        batcher = Batcher(self.batches, batch_size=10)

        batch = next(batcher.get_batch())

        assert batch == ("msg1", "msg2", "msg3")

    def test_get_yields_batches_by_size(self):
        batcher = Batcher(self.batches, batch_size=2)

        batch_generator = batcher.get_batch()
        batch = next(batch_generator)
        assert batch == ("msg1", "msg2")
        assert next(batcher.get_batch()) == ("msg3",)

    def test_raises_value_error_on_negative_batch_size(self):
        batcher = Batcher(self.batches, batch_size=-2)
        with pytest.raises(ValueError):
            next(batcher.get_batch())

    def test_raises_value_error_on_zero_batch_size(self):
        batcher = Batcher(self.batches, batch_size=0)
        with pytest.raises(ValueError):
            next(batcher.get_batch())
