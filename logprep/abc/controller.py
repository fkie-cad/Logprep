"""This general controller class, combining the input and output class"""

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.generator.http.batcher import Batcher
from logprep.generator.http.loader import FileLoader
from logprep.generator.http.sender import Sender
from logprep.util.logging import LogprepMPQueueListener

logger: Logger = logging.getLogger("Generator")


class Controller(ABC):
    """Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(self, loghandler: LogprepMPQueueListener, **config) -> None:
        self.config = config
        self.loghandler = loghandler
        self.thread_count: int = config.get("thread_count", 1)

    def setup(self):
        manipulator = Manipulator(**self.config)
        directory = manipulator.template()
        file_loader = FileLoader(directory, **self.config)
        batcher = Batcher(file_loader.read_lines(), **self.config)
        self.sender = Sender(batcher, **self.config)

    @abstractmethod
    def run(self):
        """Run the generator"""

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            future = executor.submit(self.sender.send_batch)
            future.result()
            logger.info("Finished processing all events")
