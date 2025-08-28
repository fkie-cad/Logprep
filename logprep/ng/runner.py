"""
Runner module
"""

import atexit
import logging
from logging.handlers import QueueListener
from typing import Iterator

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender
from logprep.util.configuration import Configuration
from logprep.util.logging import logqueue

logger = logging.getLogger("Runner")


class Runner:
    """Class responsible for running the log processing pipeline."""

    instance: "Runner | None" = None

    _input_connector: Input | None = None

    def __new__(cls, sender: Sender) -> "Runner":
        """Create a new Runner singleton."""
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, sender: Sender) -> None:
        self.sender = sender
        atexit.register(self.shut_down)
        self._setup_logging()

    @classmethod
    def from_configuration(cls, configuration: Configuration) -> "Runner":
        """Factory method to build and setup the Runner and its components"""
        input_iterator: Iterator = iter([])
        cls._input_connector = Factory.create(configuration.input) if configuration.input else None
        if cls._input_connector is not None:
            event_backlog = SetEventBacklog()
            cls._input_connector.event_backlog = event_backlog
            timeout = configuration.timeout
            input_iterator = cls._input_connector(timeout=timeout)
        output_connectors = [
            Factory.create({output_name: output})
            for output_name, output in configuration.output.items()
        ]
        error_output = (
            Factory.create(configuration.error_output) if configuration.error_output else None
        )
        processors = [
            Factory.create(processor_config) for processor_config in configuration.pipeline
        ]
        process_count = configuration.process_count

        pipeline = Pipeline(
            input_connector=input_iterator,
            processors=processors,
            process_count=process_count,
        )
        sender = Sender(
            pipeline=pipeline,
            outputs=output_connectors,
            error_output=error_output,
            process_count=process_count,
        )
        sender.setup()
        if cls._input_connector:
            cls._input_connector.setup()
        runner = cls(sender)
        return runner

    def run(self) -> None:
        """Run the log processing pipeline."""
        logger.debug("start log processing")
        sender = self.sender
        while 1:
            logger.debug("iterating, sender: %s", next(sender))
            for event in sender:
                logger.debug("processed event: %s", event)
        logger.debug("end log processing")

    def shut_down(self):
        """Shut down the log processing pipeline."""
        self.sender.shut_down()
        logger.info("Runner shut down complete.")
        self.log_handler.stop()

    def stop(self) -> None:
        """Stop the log processing pipeline."""
        logger.info("Stopping runner and exiting...")
        raise SystemExit(0)

    def _setup_logging(self):
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self.log_handler = QueueListener(logqueue, console_handler)
            self.log_handler.start()
