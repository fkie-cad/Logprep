import threading
from typing import Iterable

from logprep.abc.output import Output


class Sender:
    """Manages the Batcher and Output classes"""

    def __init__(self, input_events: Iterable, output: Output, **config):
        self.config = config
        self.output = output
        self.input_events = iter(input_events)
        self.target_url = config.get("target_url")
        self._lock = threading.Lock()
        if not self.target_url:
            raise ValueError("No target_url specified")

    def send_batch(self) -> None:
        """Loads a batch from the message backlog and sends to the endpoint"""
        target_url = self.target_url
        while self.input_events:
            with self._lock:
                batch = next(self.input_events)
            # line starts with the target path of the target url
            self.output.store(f"{target_url}{batch}")
