"""
This generator will parse example events, manipulate their timestamps and send them to
a defined output
"""

import logging
import time
from logging import Logger

from logprep.abc.controller import Controller

logger: Logger = logging.getLogger("Generator")


class KafkaController(Controller):
    """
    Controller for the HTTP Generator using Kafka output
    """

    def run(self) -> str:
        """
        Iterate over all event classes, trigger their processing and count the return statistics
        """
        if self.loghandler is not None:
            self.loghandler.start()
        logger.info("Started Data Processing")
        self.input.reformat_dataset()
        run_time_start = time.perf_counter()
        try:
            self._generate_load()
        except KeyboardInterrupt:
            logger.info("Gracefully shutting down...")
        self.input.clean_up_tempdir()
        run_duration = time.perf_counter() - run_time_start
        health = self.output.health()
        logger.info("Completed with a healthy kafka producer: %s", health)
        logger.info("Execution time: %f seconds", run_duration)
        if self.loghandler is not None:
            self.loghandler.stop()
        return "some stats"
