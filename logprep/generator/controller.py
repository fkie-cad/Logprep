"""This general controller class, combining the input and output class"""

import logging
import signal
import threading
import time
from types import FrameType

from logprep.abc.output import Output
from logprep.generator.input import Input
from logprep.generator.loader import FileLoader
from logprep.generator.sender import Sender
from logprep.util.logging import LogprepMPQueueListener

logger = logging.getLogger("Generator")


class Controller:
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
        self.thread_count: int = config.get("thread_count", 1)
        self.file_loader = FileLoader(self.input.temp_dir, **self.config)
        self.sender = Sender(self.file_loader.read_lines(), self.output, **self.config)
        self.exit_requested = False

    def setup(self) -> None:
        """Setup the generator"""
        self.loghandler.start()
        logger.debug("Start thread Fileloader active threads: %s", threading.active_count())
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def run(self) -> None:
        """Iterate over all event classes, trigger their processing and
        count the return statistics"""
        logger.info("Started Data Processing")
        self.input.reformat_dataset()
        self.setup()
        run_time_start = time.perf_counter()
        self.sender.send_batches()
        self.input.clean_up_tempdir()
        run_duration = time.perf_counter() - run_time_start
        stats = self.output.statistics
        logger.info("Completed with following statistics: %s", stats)
        logger.info("Execution time: %f seconds", run_duration)
        if not self.exit_requested:
            self.stop(signal.SIGTERM, None)
        self.loghandler.stop()

    def stop(self, signum: int, _frame: FrameType | None) -> None:
        """Stops the generator"""
        self.exit_requested = True
        self.sender.stop()
        self.file_loader.close()
        logger.info("Stopped Data Processing on signal %s", signum)
