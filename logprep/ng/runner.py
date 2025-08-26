"""
Runner module
"""

import logging

from logprep.factory import Factory
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender
from logprep.util.configuration import Configuration

logger = logging.getLogger("Runner")


class Runner:
    """Class responsible for running the log processing pipeline."""

    should_exit = False

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
        return cls(sender)

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

    def stop(self) -> None:
        self.should_exit = True
