import logging
import threading
from typing import Dict, Generator, Iterable

from logprep.util.defaults import DEFAULT_BATCH_SIZE

logger = logging.getLogger("Batcher")


class Batcher:
    """Batches messages from an EventBuffer and forwards them in controlled batches."""

    def __init__(self, input_events: Iterable[str], **config) -> None:
        self.batch_size: int = config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.input_events = iter(input_events)
        self.lock = threading.Lock()
        self._batches: Dict[str, str] = {}

    @property
    def batches(self) -> Generator[str, None, None]:
        "Batch data into tuples of length n. The last batch may be shorter."
        if self.batch_size < 1:
            raise ValueError("'batch_size' must be at least one")
        with self.lock:
            if self.batch_size == 1:
                raise NotImplementedError("Batch size of 1 is not supported")
            for event in self.input_events:
                path, _, message = event.partition(",")
                if path not in self._batches:
                    self._batches[path] = event
                else:
                    self._batches[path] += f";{message}"
                    if self._batches[path].count(";") + 1 >= self.batch_size:
                        message = self._batches.pop(path)
                        yield f"{message}\n"
            while self._batches:
                path, message = self._batches.popitem()
                while message.count(";") + 1 < self.batch_size:
                    if message.count(";") == 0:
                        last_message = message.rpartition(",")[-1]
                        message = f"{message};{last_message}\n"
                    else:
                        last_message = message.rpartition(";")[-1]
                        message = f"{message};{last_message}\n"
                yield message
