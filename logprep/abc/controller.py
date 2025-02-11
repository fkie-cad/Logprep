"""
This general controller class, combining the input and output class
"""

import logging
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.abc.output import Output
from logprep.generator.http.input import Input
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger: Logger = logging.getLogger("Generator")


class Controller:
    """
    Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(self, output: Output, **kwargs) -> None:
        self.config = kwargs
        self.loghandler = None
        self._setup_logging()
        self.thread_count: int = kwargs.get("thread_count", 1)
        self.input: Input = Input(self.config)
        self.output = output

    @abstractmethod
    def run(self): ...

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if self.config.get("loglevel"):
            logging.getLogger().setLevel(self.config.get("loglevel"))
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.loghandler = LogprepMPQueueListener(logqueue, console_handler)
            self.loghandler.start()

    def _generate_load(self):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            executor.map(self.output.store, self.input.load())
