"""This general controller class, combining the input and output class"""

import logging
import signal
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        print(f"Start thread Fileloader active threads: {threading.active_count()}")
        batcher = Batcher(self.file_loader.read_lines(), **self.config)
        self.sender = Sender(batcher, self.output, **self.config)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    @abstractmethod
    def run(self):
        """Run the generator"""

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            futures = {executor.submit(self.sender.send_batch) for _ in range(self.thread_count)}

            for future in as_completed(futures):
                result = future.result()  # Wait for a completed task
                print(f"During generate load active threads: {threading.active_count()}")
                print(f"{result=}")
                logger.info("Finished processing a batch")

        print(f"After generate load active threads: {threading.active_count()}")

    def stop(self, signum, frame):
        self.file_loader.close()
        logger.info("Stopped Data Processing on signal %s", signum)
        return None
