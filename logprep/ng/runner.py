"""
Runner module
"""

import json
import logging
import logging.config
import os
import warnings
from typing import cast

from attrs import asdict

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG

logger = logging.getLogger("Runner")


class Runner:
    """Class, a singleton runner, responsible for running the log processing pipeline."""

    instance: "Runner | None" = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)

        return cls.instance

    def __init__(self, configuration) -> None:
        """Initialize the runner from the given `configuration`.

        Component wiring is deferred to `setup()` to preserve the required init order.
        """

        self.configuration = configuration
        self._running_config_version = configuration.version

        # Initialized in `setup()`; updated by runner logic thereafter.
        self.should_exit: bool | None = None
        self.input_connector: Input | None = None
        self.output_connectors: list[Output] | None = None
        self.error_output: Output | None = None
        self.processors: list[Processor] | None = None
        self.pipeline: Pipeline | None = None
        self.sender: Sender | None = None

        self.setup()

    def _initialize_and_setup_input_connectors(self):
        self.input_connector = (
            Factory.create(self.configuration.input) if self.configuration.input else None
        )
        if self.input_connector is not None:
            self.input_connector.event_backlog = SetEventBacklog()
            self.input_connector.setup()
        else:
            logger.warning("No input connector configured.")

    def _initialize_and_setup_output_connectors(self):
        self.output_connectors = [
            Factory.create({output_name: output})
            for output_name, output in self.configuration.output.items()
        ]

        for i, output_connector in enumerate(self.output_connectors):
            if output_connector is not None:
                output_connector.setup()
            else:
                logger.warning(
                    f"Could not setup one of the output connectors ({i}/{len(self.output_connectors)})."
                )

    def _initialize_and_setup_error_outputs(self):
        self.error_output = (
            Factory.create(self.configuration.error_output)
            if self.configuration.error_output
            else None
        )

        if self.error_output is not None:
            self.error_output.setup()
        else:
            logger.warning("No error output configured.")

    def _initialize_and_setup_processors(self):
        self.processors = [
            Factory.create(processor_config) for processor_config in self.configuration.pipeline
        ]

        if not self.processors:
            logger.warning("No processor configured.")

        for i, processor in enumerate(self.processors):
            if processor is not None:
                processor.setup()
            else:
                logger.warning(
                    f"Could not setup one of the processors ({i}/{len(self.processors)})."
                )

    def _initialize_and_setup_pipeline(self):
        if self.input_connector is None:
            logger.debug("Runner._initialize_and_setup_pipeline: No input connector configured.")
            raise AttributeError(
                "No input connector configured. Pipeline needs a configured input connector."
            )

        input_iterator = self.input_connector(timeout=self.configuration.timeout)
        self.pipeline = Pipeline(
            input_connector=input_iterator,
            processors=self.processors,
            process_count=self.configuration.process_count,
        )
        self.pipeline.setup()

    def _initialize_and_setup_sender(self):
        self.sender = Sender(
            pipeline=self.pipeline,
            outputs=cast(list[Output], self.output_connectors),
            error_output=self.error_output,
            process_count=self.configuration.process_count,
        )
        self.sender.setup()

    def run(self) -> None:
        """Cli function to run the log processing pipeline."""

        # TODO:
        # * integration tests

        self.configuration.schedule_config_refresh()

        while True:
            if self.should_exit:
                logger.debug("Runner exiting.")
                break

            logger.debug("Runner processing loop.")

            logger.debug("Check configuration change before processing a batch of events.")
            self.configuration.refresh()

            if self.configuration.version != self._running_config_version:
                self.reload()

            logger.debug("Process next batch of events.")
            self._process_events()

        self.shut_down()
        logger.debug("End log processing.")

    def _process_events(self) -> None:
        """Process a batch of events got from sender iterator."""

        if not self.sender:
            return

        logger.debug("Start log processing.")

        logger.debug(f"Get batch of events from sender ({self.sender.batch_size=}).")
        for event in self.sender:
            if event is None:
                continue

            if event.state == EventStateType.FAILED:
                logger.error("event failed: %s", event)
            else:
                logger.debug("event processed: %s", event.state)

        logger.debug("Finished processing batch of events.")

    def setup(self) -> None:
        """Set up the runner, its components, and required runner attributes.

        Note:
            Keep the order of `_initialize_...` calls, and ensure that certain
            runner attributes are set correctly to maintain the expected logic.
        """

        self.should_exit = False

        # init and setup components in order:
        self._initialize_and_setup_input_connectors()
        self._initialize_and_setup_output_connectors()
        self._initialize_and_setup_error_outputs()
        self._initialize_and_setup_processors()
        self._initialize_and_setup_pipeline()
        self._initialize_and_setup_sender()

    def shut_down(self) -> None:
        """Shut down the log processing pipeline.

        Note:
            Keep the order of `...shut_down()` calls, and ensure that certain
            runner attributes are set correctly to maintain the expected logic.
        """

        self.should_exit = True

        # shutdowns in reversed order of setup():
        if self.sender is not None:
            self.sender.shut_down()

        if self.pipeline is not None:
            self.pipeline.shut_down()

        if self.processors is not None:
            for processor in self.processors:
                if processor is not None:
                    processor.shut_down()

        if self.error_output is not None:
            self.error_output.shut_down()

        if self.output_connectors is not None:
            for output_connector in self.output_connectors:
                if output_connector is not None:
                    output_connector.shut_down()

        if self.input_connector is not None:
            self.input_connector.shut_down()

        logger.info("Runner shut down complete.")

    def stop(self) -> None:
        """Cli function to stop the log processing pipeline."""

        logger.info("Stopping runner and exiting...")
        self.should_exit = True

    def setup_logging(self) -> None:
        """Setup the logging configuration.
        is called in the :code:`logprep.run_logprep` module.
        We have to write the configuration to the environment variable :code:`LOGPREP_LOG_CONFIG` to
        make it available for the uvicorn server in :code:'logprep.util.http'.
        """

        warnings.simplefilter("always", DeprecationWarning)
        logging.captureWarnings(True)
        log_config = DEFAULT_LOG_CONFIG | asdict(self.configuration.logger)
        os.environ["LOGPREP_LOG_CONFIG"] = json.dumps(log_config)
        logging.config.dictConfig(log_config)

    def reload(self) -> None:
        """Reload the log processing pipeline."""

        logger.info("Reloading log processing pipeline...")

        self.shut_down()
        self.setup()

        self._running_config_version = self.configuration.version
        self.configuration.schedule_config_refresh()
        logger.info("Finished reloading log processing pipeline.")
