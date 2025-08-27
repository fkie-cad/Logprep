"""
Runner module
"""

import atexit
import logging

from logprep.factory import Factory
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender
from logprep.util.configuration import Configuration

logger = logging.getLogger("Runner")


class Runner:
    """Class responsible for running the log processing pipeline."""

    should_exit: bool = False

    instance: "Runner | None" = None

    def __new__(cls, sender: Sender) -> "Runner":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, sender: Sender) -> None:
        self.sender = sender

    @classmethod
    def from_configuration(cls, configuration: Configuration) -> "Runner":
        """Factory method to build the Runner"""
        input_connector = Factory.create(configuration.input) if configuration.input else None
        timeout = configuration.timeout
        input_iterator = iter([]) if input_connector is None else input_connector(timeout=timeout)
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

        pipeline = Pipeline(
            input_connector=input_iterator,
            processors=processors,
            process_count=configuration.process_count,
        )
        sender = Sender(pipeline=pipeline, outputs=output_connectors, error_output=error_output)
        sender.setup()
        runner = cls(sender)
        atexit.register(runner.shut_down)
        return runner

    def run(self) -> None:
        """Run the log processing pipeline."""
        logger.debug("start log processing")
        sender = self.sender
        while 1:
            if self.should_exit:
                break
            for event in sender:
                logger.debug("processed event: %s", event)
                if self.should_exit:
                    break

    def shut_down(self):
        """Shut down the log processing pipeline."""
        self.sender.shut_down()

    def stop(self) -> None:
        """Stop the log processing pipeline."""
        raise SystemExit(0)
