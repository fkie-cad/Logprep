"""This general controller class, combining the input and output class"""

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.abc.output import Output
from logprep.generator.http.input import Input
from logprep.util.logging import LogprepMPQueueListener

logger: Logger = logging.getLogger("Generator")


class Controller(ABC):
    """Generally Controls the workflow of the generator by reading inputs, manipulating events
    and sending them to outputs
    """

    def __init__(
        self,
        input_connector: Input,
        output_connector: Output,
        loghandler: LogprepMPQueueListener,
        **kwargs,
    ) -> None:
        self.config = kwargs
        self.loghandler = loghandler
        self.thread_count: int = kwargs.get("thread_count", 1)
        self.input = input_connector
        self.output = output_connector

    @abstractmethod
    def run(self):
        """Run the generator"""

    def _generate_load(self):

        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            executor.map(self.output.store, self.input.load())
