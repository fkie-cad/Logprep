"""This general controller class, combining the input and output class"""

import logging
import signal
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from logprep.abc.output import Output
from logprep.generator.http.input import Input
from logprep.generator.http.loader import FileLoader
from logprep.generator.http.sender import Sender
from logprep.util.logging import LogprepMPQueueListener

logger = logging.getLogger("Generator")


class Controller(ABC):
    """Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(
        self,
        output_connector: Output,
        input_connector: Input,
        loghandler: LogprepMPQueueListener,
        **config,
    ) -> None:
        self.output = output_connector
        self.input = input_connector
        self.loghandler = loghandler
        self.config = config
        self.sender = None
        self.thread_count: int = config.get("thread_count", 1)
        self.file_loader = FileLoader(self.input.temp_dir, **self.config)
        self.exit_requested = False
        # TODO:
        # implement shuffle in batcher
        # implement handling in batcher for different paths
        #
        # revise logging (no logs in controller about threading)
        # interrupt (SIGINT) in threadpoolexecutor with high event count
        #
        # refactor input class with focus on Single Responsibility Principle
        # how to handle big amount of example events? they are loaded in memory
        # test with big files
        # compute message backlog size instead of defaults?

    def setup(self) -> None:
        self.loghandler.start()
        logger.debug("Start thread Fileloader active threads: %s", threading.active_count())
        self.sender = Sender(self.file_loader.read_lines(), self.output, **self.config)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    @abstractmethod
    def run(self):
        """Run the generator"""

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            futures = {executor.submit(self.sender.send_batch) for _ in range(self.thread_count)}
            for future in as_completed(futures):
                if self.exit_requested:
                    logger.debug("--------------- Exit requested ---------------")
                    break
                future.result()
                logger.debug("During generate load active threads: %s", threading.active_count())
                logger.debug("Finished processing a batch")

        logger.debug("After generate load active threads: %s", threading.active_count())

    def stop(self, signum, frame):
        self.exit_requested = True
        self.sender.stop()
        self.file_loader.close()
        logger.info("Stopped Data Processing on signal %s", signum)
        return None
