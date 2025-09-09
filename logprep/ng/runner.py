"""
Runner module
"""

import logging
from logging.handlers import QueueListener
from queue import Queue
from typing import Iterator

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.connector.http.input import HttpInput
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import LogprepReloadException, Sender
from logprep.util.configuration import Configuration
from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE
from logprep.util.logging import logqueue

logger = logging.getLogger("Runner")


class Runner:
    """Class responsible for running the log processing pipeline."""

    instance: "Runner | None" = None

    _input_connector: Input | None = None

    _configuration: Configuration

    _config_version: str

    _log_handler: QueueListener | None = None

    def __new__(cls, sender: Sender) -> "Runner":
        """Create a new Runner singleton."""
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, sender: Sender) -> None:
        self.sender = sender
        self._setup_logging()

    @classmethod
    def from_configuration(cls, configuration: Configuration) -> "Runner":
        """Factory method to build and setup the Runner and its components"""
        sender = cls.get_sender(configuration)
        runner = cls(sender)
        runner._configuration = configuration
        runner._config_version = configuration.version
        runner.setup()
        return runner

    @classmethod
    def get_sender(cls, configuration) -> Sender:
        """Create the sender for the log processing pipeline."""
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
        return sender

    def run(self) -> None:
        """Run the log processing pipeline."""

        self._configuration.schedule_config_refresh()
        while 1:
            try:
                self._process_events()
            except LogprepReloadException:
                self.reload()

        logger.debug("end log processing")

    def _process_events(self) -> None:
        logger.debug("start log processing")
        sender = self.sender
        configuration = self._configuration
        config_version = configuration.version
        for event in sender:
            if event.state == EventStateType.FAILED:
                logger.error("event failed: %s", event)
            else:
                logger.debug("event processed: %s", event.state)

            configuration.refresh()
            if configuration.version != config_version:
                raise LogprepReloadException("Configuration change detected, reloading...")

    def setup(self) -> None:
        """Setup the runner and its components."""
        self.sender.setup()
        if self._input_connector:
            input_type = self._input_connector._config.type  # pylint: disable=protected-access
            if "http_input" in input_type:
                self._set_http_input_queue()
            self._input_connector.setup()

    def shut_down(self) -> None:
        """Shut down the log processing pipeline."""
        self.sender.shut_down()
        logger.info("Runner shut down complete.")
        if self._input_connector:
            self._input_connector.shut_down()
        if self._log_handler:
            self._log_handler.stop()

    def stop(self) -> None:
        """Stop the log processing pipeline."""
        logger.info("Stopping runner and exiting...")
        self.shut_down()
        raise SystemExit(0)

    def _setup_logging(self) -> None:
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
            self._log_handler = QueueListener(logqueue, console_handler)
            self._log_handler.start()

    def reload(self) -> None:
        """Reload the log processing pipeline."""
        logger.debug("Reloading log processing pipeline...")
        self._config_version = self._configuration.version
        self.sender.shut_down()
        self.sender = Runner.get_sender(self._configuration)
        self.sender.setup()
        if self._input_connector:
            self._input_connector.setup()
        self._configuration.schedule_config_refresh()
        logger.debug("Finished reloading log processing pipeline.")

    def _set_http_input_queue(self):
        """
        this workaround has to be done because the queue size is not configurable
        after initialization and the queue has to be shared between the multiple processes
        """
        input_config = list(self._configuration.input.values())
        input_config = input_config[0] if input_config else {}
        is_http_input = input_config.get("type") == "http_input"
        if not is_http_input and HttpInput.messages is not None:
            return
        message_backlog_size = input_config.get(
            "message_backlog_size", DEFAULT_MESSAGE_BACKLOG_SIZE
        )
        HttpInput.messages = Queue(maxsize=message_backlog_size)
