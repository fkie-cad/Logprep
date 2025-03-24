"""The Sender class, which loads the messages from input and forwards them
to output, to be send to the end point"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from typing import Iterable

from logprep.abc.output import Output

logger = logging.getLogger("Sender")


class Sender:
    """Manages the Batcher and Output classes"""

    def __init__(self, input_events: Iterable, output: Output, **config):
        self.config = config
        self.output = output
        self.thread_count = config.get("thread_count", 1)
        self.input_events = iter(input_events)
        self.exit_requested = False

    def send_batches(self) -> None:
        """Loads a batch from the message backlog and sends to the endpoint"""
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            while not self.exit_requested:
                chunk = tuple(islice(self.input_events, self.thread_count))
                if not chunk:
                    break
                for _ in executor.map(self.output.store, chunk):
                    logger.debug(
                        "During generate load active threads: %s", threading.active_count()
                    )
        logger.debug("After generate load active threads: %s", threading.active_count())

    def stop(self) -> None:
        """Stops the sender"""
        self.exit_requested = True
