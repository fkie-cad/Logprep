"""
This general controller class, combining the input and output class
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.generator.http.input import Input
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger: Logger = logging.getLogger("Generator")


class Controller:
    """
    Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(self, **kwargs):
        self.config = kwargs
        self.loghandler = None
        self._setup_logging()
        self.thread_count: int = kwargs.get("thread_count")
        self.input: Input = Input(self.config)
        self.output = self._create_output(kwargs)

    def _create_output(self, kwargs):
        """To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement `_create_output`")

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if self.config.get("loglevel"):
            logging.getLogger().setLevel(self.config.get("loglevel"))
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def run(self):
        raise NotImplementedError("Subclasses must implement `run`")

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            executor.map(self.output.store, self.input.load())
