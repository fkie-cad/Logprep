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
    Controls the workflow of the generator by reading inputs, manipulating events and sending them to
    outputs
    """

    def __init__(self, **kwargs):
        self.config = kwargs
        self._setup_logging()
        self.thread_count: int = kwargs.get("thread_count")
        self.use_reporter: bool = kwargs.get("report")
        self.input: Input = Input(self.config)
        output_config = {
            "generator_output": {
                "type": "http_output",
                "user": kwargs.get("user"),
                "password": kwargs.get("password"),
                "target_url": kwargs.get("target_url"),
            }
        }
        self.output: HttpOutput = Factory.create(output_config)

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def run(self):
        """
        Iterate over all event classes, trigger their processing and count the return statistics
        """
        # TODO use a logprep pipeline to handle processing
        logger.info("Started Data Processing")
        self.input.reformat_dataset()
        run_time_start = time.perf_counter()
        try:
            self._generate_load()
        except KeyboardInterrupt:
            logger.info("Gracefully shutting down...")
        self.input.clean_up_tempdir()
        run_duration = time.perf_counter() - run_time_start
        stats = self.output.metrics.status_codes.tracker.collect()[0].samples
        logger.info("Completed with following http return code statistics: %s", stats)
        logger.info("Execution time: %f seconds", run_duration)
        self.loghandler.stop()

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            results = executor.map(self.output.store, self.input.load())
