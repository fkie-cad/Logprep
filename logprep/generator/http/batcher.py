import logging
from itertools import islice
from typing import Generator, Iterable, List, Tuple

from logprep.util.defaults import DEFAULT_BATCH_SIZE

logger = logging.getLogger("Batcher")


class Batcher:
    """Batches messages from an EventBuffer and forwards them in controlled batches."""

    def __init__(self, batches: Iterable, batch_size: int = DEFAULT_BATCH_SIZE):
        self.events = batches
        self.batch_size = batch_size
        self._batch: List[str] = []

    def get_batch(self) -> Generator[Tuple[str], None, None]:
        "Batch data into tuples of length n. The last batch may be shorter."
        # TODO: Refactor this method to itertools.batched if support for 3.11 is dropped
        if self.batch_size < 1:
            raise ValueError("'batch_size' must be at least one")
        it = iter(self.events)
        while batch := tuple(islice(it, self.batch_size)):
            yield batch
