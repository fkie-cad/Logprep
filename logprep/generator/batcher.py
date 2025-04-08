""" "
This module provides a `Batcher` class that batches input events into specified
sizes for a specified number of events.

Classes:
    Batcher: A class to batch input events into specified sizes for a specified number of events.

Usage example:

    >>> input_events = ["path1,event1", "path2,event2", "path1,event3"]
    >>> batcher = Batcher(input_events, batch_size=2, events=3)
    >>> for batch in batcher:
            print(batch)
"""

import itertools
import random
from typing import Dict, Generator, Iterable

from logprep.util.defaults import DEFAULT_BATCH_SIZE


class Batcher:
    """A class to batch input events into specified sizes for a specified
    number of events.
    """

    def __init__(self, input_events: Iterable[str], **config) -> None:
        self.batch_size: int = config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.event_count = config.get("events", 1)
        shuffle = config.get("shuffle", False)
        rng_seed = config.get("rng", None)
        self.rng = random.Random(rng_seed)
        if shuffle:
            input_events = list(input_events)
            self.rng.shuffle(input_events)

        self.event_generator = itertools.cycle(input_events)
        self._batch_mapping: Dict[str, str] = {}

    def __next__(self):
        return next(self._batches)

    def __iter__(self):
        return self

    @property
    def _batches(self) -> Generator[str, None, None]:
        """
        Generates batches of events from the event generator.
        Yields
        ------
        str
            A batch of events as a string, each event separated by a semicolon.
            The string starts with the path of the event.
        Raises
        ------
        ValueError
            If `batch_size` is less than one.
        Notes
        -----
        - The method continuously fetches events from `self.event_generator`.
        - If `batch_size` is 1, each event is yielded immediately.
        - Events are grouped by their path, and messages are concatenated with a semicolon.
        - When the batch size for a path is reached or no more events are left,
        the batch is yielded.
        """

        if self.batch_size < 1:
            raise ValueError("'batch_size' must be at least one")
        for event in self.event_generator:
            if self.event_count == 0:
                for path in self._batch_mapping:
                    message = self._batch_mapping.pop(path)
                    yield f"{message}\n"
                break

            self.event_count -= 1
            if self.batch_size == 1:
                yield f"{event}\n"
            path, _, message = event.partition(",")
            if path not in self._batch_mapping:
                self._batch_mapping[path] = event
            else:
                self._batch_mapping[path] += f";{message}"
            if self._batch_size_reached(path):
                message = self._batch_mapping.pop(path)
                yield f"{message}\n"

    def _batch_size_reached(self, path):
        return self._batch_mapping[path].count(";") + 1 == self.batch_size
