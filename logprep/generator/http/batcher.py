import logging
import time
from typing import List

from logprep.abc.output import Output
from logprep.generator.http.loader import FileLoader
from logprep.util.defaults import DEFAULT_BATCH_SIZE, DEFAULT_BATCH_TIME

logger = logging.getLogger("Batcher")


class Batcher:
    """Batches messages from an EventBuffer and forwards them in controlled batches."""

    def __init__(
        self,
        file_loader: FileLoader,
        output: Output,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_time: float = DEFAULT_BATCH_TIME,
    ):

        self.file_loader = file_loader
        self.batch_size = batch_size
        self.batch_time = batch_time
        self.output = output

    def process_batches(self):
        """Processes messages from EventBuffer and sends them in batches."""
        batch = []
        last_sent_time = time.time()

        with self.file_loader as file_loader:
            for message in file_loader.read_lines():
                batch.append(message)
                if len(batch) >= self.batch_size:
                    self._send_batch(batch)
                    batch = []
                    last_sent_time = time.time()

                if (time.time() - last_sent_time) >= self.batch_time and batch:
                    self._send_batch(batch)
                    batch = []
                    last_sent_time = time.time()
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[str]):
        logger.info("Sending batch of %s messages.", len(batch))
        self.output(batch)
