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
        self.exit_requested = False
        if not self.target_url:
            raise ValueError("No target_url specified")

    def send_batch(self) -> None:
        """Loads a batch from the message backlog and sends to the endpoint"""
        target_url = self.target_url
        while not self.exit_requested:
            try:
                with self._lock:
                    batch = next(self.input_events)
            except StopIteration:
                break
            # line starts with the target path of the target url
            self.output.store(f"{target_url}{batch}")

    def stop(self) -> None:
        """Stops the sender"""
        self.exit_requested = True
