"""
This generator will parse example events, manipulate their timestamps and send them to
a defined output
"""

import logging
import time
from logging import Logger

from logprep.abc.controller import Controller
from logprep.connector.http.output import HttpOutput
from logprep.factory import Factory

logger: Logger = logging.getLogger("Generator")


class HTTPController(Controller):
    """
    Controller for the HTTP Generator
    """

    def create_output(self, kwargs):
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
        return self.output

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
