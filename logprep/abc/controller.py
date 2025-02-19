"""This general controller class, combining the input and output class"""

import logging
import signal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.abc.output import Output
from logprep.generator.http.batcher import Batcher
from logprep.generator.http.loader import FileLoader
from logprep.generator.http.sender import Sender
from logprep.util.logging import LogprepMPQueueListener

logger: Logger = logging.getLogger("Generator")


class Controller(ABC):
    """Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(self, output: Output, loghandler: LogprepMPQueueListener, **config) -> None:
        self.output = output
        self.loghandler = loghandler
        self.config = config
        self.sender = None
        self.thread_count: int = config.get("thread_count", 1)
        directory = "/tmp/generator"
        self.file_loader = FileLoader(directory, **self.config)
        # TODO:
        # threadpoolexecutor nachlesen und fixen https://docs.python.org/3.11/library/concurrent.futures.html
        # threads sollen sich beenden
        #
        # ekneg54:
        # logging zum laufen bringen
        # manipulator muss refactored werden
        # testen mit wirklichem output

    def setup(self):
        # manipulator = Manipulator(**self.config)
        # directory = manipulator.template()
        self.file_loader.start()
        batcher = Batcher(self.file_loader.read_lines(), **self.config)
        self.sender = Sender(batcher, self.output, **self.config)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    @abstractmethod
    def run(self):
        """Run the generator"""

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            while True:
                future = executor.submit(self.sender.send_batch)
                result = future.result()
                print(f"{result=}")
                if not result:
                    break
                logger.info("Finished processing all events")

    def stop(self, signum, frame):
        self.file_loader.close()
        logger.info("Stopped Data Processing on signal %s", signum)
        return None
