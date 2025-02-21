import itertools
import logging
from typing import Dict, Generator, Iterable

from logprep.util.defaults import DEFAULT_BATCH_SIZE

logger = logging.getLogger("Batcher")


class Batcher:
    """Batches messages from an EventBuffer and forwards them in controlled batches."""

    def __init__(self, input_events: Iterable[str], **config) -> None:
        self.batch_size: int = config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.event_count = config.get("events", 1)
        self.input_events = iter(input_events)
        self._batches: Dict[str, str] = {}

    @property
    def batches(self) -> Generator[str, None, None]:
        "Batch data into tuples of length n. The last batch may be shorter."
        if self.batch_size < 1:
            raise ValueError("'batch_size' must be at least one")
        for event in itertools.cycle(self.input_events):
            if self.event_count == 0:
                break
            if self.batch_size == 1:
                self.event_count -= 1
                yield f"{event}\n"
            path, _, message = event.partition(",")
            if path not in self._batches:
                self._batches[path] = event
                self.event_count -= 1
            else:
                self._batches[path] += f";{message}"
                self.event_count -= 1
                if self.event_count == 0 or self._batches[path].count(";") + 1 >= self.batch_size:
                    message = self._batches.pop(path)
                    yield f"{message}\n"
        while self._batches and self.event_count > 0:
            path, message = self._batches.popitem()
            while message.count(";") + 1 < self.batch_size:
                if message.count(";") == 0:
                    last_message = message.rpartition(",")[-1]
                    message = f"{message};{last_message}\n"
                else:
                    last_message = message.rpartition(";")[-1]
                    message = f"{message};{last_message}\n"
            yield message
