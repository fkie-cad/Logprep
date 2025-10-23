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
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG

logger = logging.getLogger("Runner")


class Runner:
    """Class, a singleton runner, responsible for running the log processing pipeline."""

    instance: "Runner | None" = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)

        return cls.instance

    def __init__(self, configuration: Configuration) -> None:
        """Initialize the runner from the given `configuration`.

        Component wiring is deferred to `setup()` to preserve the required init order.
        """

        self.configuration = configuration
        self._running_config_version = configuration.version
        self._input_connector: Input | None = None

        # Initialized in `setup()`; updated by runner logic thereafter:
        self.should_exit: bool | None = None
        self.sender: Sender | None = None

        self.setup()

    def _initialize_pipeline(self) -> Pipeline:
        """Initialize the pipeline from the given `configuration`.

        This method performs the following tasks:

        - Creates components based on the configuration:
          - input connector
          - processors

        - Sets up the input connector:
          - attaches an event backlog
          - calls its `setup()` method
          - initializes its iterator with the configured timeout

        - Validates that:
          - an input connector is configured
          - all processors are properly configured

        - Instantiates the `Pipeline` with:
          - the input connector iterator
          - the list of processors

        Returns
        -------
        Pipeline
            The instantiated pipeline instance (not yet set up).
        """

        self._input_connector = cast(Input, Factory.create(self.configuration.input))
        self._input_connector.event_backlog = SetEventBacklog()
        self._input_connector.setup()

        input_iterator = self._input_connector(timeout=self.configuration.timeout)
        processors = cast(
            list[Processor],
            [Factory.create(processor_config) for processor_config in self.configuration.pipeline],
        )

        return Pipeline(
            log_events_iter=input_iterator,
            processors=cast(list[Processor], processors),
        )

    def _initialize_sender(self) -> Sender:
        """Initialize the sender from the given `configuration`.

        This method performs the following tasks:

        - Creates components based on the configuration:
          - output connectors
          - error output

        - Validates that:
          - all output connectors are configured
          - an error output is available

        - Instantiates the `Sender` with:
          - the initialized pipeline
          - configured outputs
          - configured error output
          - process count from configuration

        Returns
        -------
        Sender
            The instantiated sender instance (not yet set up).
        """

        output_connectors = cast(
            list[Output],
            [
                Factory.create({output_name: output})
                for output_name, output in self.configuration.output.items()
            ],
        )

        error_output: Output | None = (
            Factory.create(self.configuration.error_output)
            if self.configuration.error_output
            else None
        )

        if error_output is None:
            logger.warning("No error output configured.")

        return Sender(
            pipeline=self._initialize_pipeline(),
            outputs=cast(list[Output], output_connectors),
            error_output=error_output,
            process_count=self.configuration.process_count,
        )

    def run(self) -> None:
        """Run the runner and continuously process events until stopped.

        This method starts the main processing loop, refreshes the configuration
        if needed, processes event batches, and only exits once `stop()` has been
        called (setting `should_exit` to True). At the end, it shuts down all
        components gracefully.
        """

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

        logger.debug("Start log processing.")

        sender = cast(Sender, self.sender)
        logger.debug(f"Get batch of events from sender (batch_size={sender.batch_size}).")
        for event in sender:
            if event is None:
                continue

            if event.state == EventStateType.FAILED:
                logger.error("event failed: %s", event)
            else:
                logger.debug("event processed: %s", event.state)

        logger.debug("Finished processing batch of events.")

    def setup(self) -> None:
        """Set up the runner, its components, and required runner attributes."""

        self.sender = self._initialize_sender()
        self.sender.setup()
        self.should_exit = False

        logger.info("Runner set up complete.")

    def shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        self.should_exit = True
        cast(Sender, self.sender).shut_down()
        self.sender = None

        input_connector = cast(Input, self._input_connector)
        input_connector.acknowledge()

        len_delivered_events = len(input_connector.event_backlog.get(EventStateType.DELIVERED))
        if len_delivered_events:
            logger.error(
                f"Input connector has {len_delivered_events} non-acked events in event_backlog."
            )

        logger.info("Runner shut down complete.")

    def stop(self) -> None:
        """Stop the runner and signal the underlying processing pipeline to exit.

        This method sets the `should_exit` flag to True, which will cause the
        runner and its components to stop gracefully.
        """

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
