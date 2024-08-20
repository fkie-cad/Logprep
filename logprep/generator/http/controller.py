"""
This generator will parse example events, manipulate their timestamps and send them to
a defined output
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.connector.http.output import HttpOutput
from logprep.factory import Factory
from logprep.generator.http.input import Input
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger: Logger = logging.getLogger("Generator")


class Controller:
    """
    Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(self, **kwargs):
        self.config = kwargs
        self.loghandler = None
        self._setup_logging()
        self.thread_count: int = kwargs.get("thread_count")
        self.input: Input = Input(self.config)
        output_config = {
            "generator_output": {
                "type": "http_output",
                "user": kwargs.get("user"),
                "password": kwargs.get("password"),
                "target_url": kwargs.get("target_url"),
                "timeout": kwargs.get("timeout", 2),
            }
        }
        self.output: HttpOutput = Factory.create(output_config)

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if self.config.get("loglevel"):
            logging.getLogger().setLevel(self.config.get("loglevel"))
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def run(self) -> str:
        """
        Iterate over all event classes, trigger their processing and count the return statistics
        """
        logger.info("Started Data Processing")
        self.input.reformat_dataset()
        run_time_start = time.perf_counter()
        try:
            self._generate_load()
        except KeyboardInterrupt:
            logger.info("Gracefully shutting down...")
        self.input.clean_up_tempdir()
        run_duration = time.perf_counter() - run_time_start
        stats = self.output.statistics
        logger.info("Completed with following statistics: %s", stats)
        logger.info("Execution time: %f seconds", run_duration)
        if self.loghandler is not None:
            self.loghandler.stop()
        return stats

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            executor.map(self.output.store, self.input.load())
