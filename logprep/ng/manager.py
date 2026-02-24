"""
Runner module
"""

import logging
import typing
from typing import cast

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.worker.types import SizeLimitedQueue
from logprep.ng.util.worker.worker import TransferWorker, Worker, WorkerOrchestrator

logger = logging.getLogger("PipelineManager")


MAX_QUEUE_SIZE = 100_000

BATCH_SIZE = 2_500
BATCH_INTERVAL_S = 5


class PipelineManager:
    """Orchestrator class managing pipeline inputs, processors and outputs"""

    def __init__(self, configuration: Configuration) -> None:
        """Initialize the component from the given `configuration`."""

        self.configuration = configuration

    def _setup(self):
        self._event_backlog = SetEventBacklog()

        self._input_connector = cast(Input, Factory.create(self.configuration.input))
        self._input_connector.event_backlog = self._event_backlog  # TODO needs to be disentagled
        self._input_connector.setup()

        processors = [
            typing.cast(Processor, Factory.create(processor_config))
            for processor_config in self.configuration.pipeline
        ]
        for processor in processors:
            processor.setup()

        self._pipeline = Pipeline(processors)

        output_connectors = [
            typing.cast(Output, Factory.create({output_name: output}))
            for output_name, output in self.configuration.output.items()
        ]

        error_output = (
            typing.cast(Output, Factory.create(self.configuration.error_output))
            if self.configuration.error_output
            else None
        )

        if error_output is None:
            logger.warning("No error output configured.")

        self._sender = Sender(outputs=output_connectors, error_output=error_output)
        self._sender.setup()

        self._orchestrator = self._create_orchestrator()

    def _create_orchestrator(self) -> WorkerOrchestrator:
        input_worker: Worker[LogEvent, LogEvent] = TransferWorker(
            name="input_worker",
            batch_size=1,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=self._input_connector(timeout=self.configuration.timeout),
            out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        )

        async def process(batch: list[LogEvent]) -> list[LogEvent]:
            return [self._pipeline.process(event) for event in batch]

        processing_worker: Worker[LogEvent, LogEvent] = Worker(
            name="processing_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=input_worker.out_queue,  # type: ignore
            out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
            handler=process,
        )

        async def send(batch: list[LogEvent]) -> list[LogEvent]:
            return self._sender.process(batch)

        output_worker: Worker[LogEvent, LogEvent] = Worker(
            name="output_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=processing_worker.out_queue,  # type: ignore
            out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
            handler=send,
        )

        acknowledge_worker: Worker[LogEvent, LogEvent] = Worker(
            name="acknowledge_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=output_worker.out_queue,  # type: ignore
            out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
            handler=self._process_sent_events,
        )

        return WorkerOrchestrator(
            workers=[input_worker, processing_worker, output_worker, acknowledge_worker]
        )

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""

        self._setup()
        await self._orchestrator.run()

    async def shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        if self._orchestrator is not None:
            await self._orchestrator.shut_down(1)

        if self._sender is not None:
            self._sender.shut_down()
        self._input_connector.acknowledge()

        len_delivered_events = len(
            list(self._input_connector.event_backlog.get(EventStateType.DELIVERED))
        )
        if len_delivered_events:
            logger.error(
                "Input connector has %d non-acked events in event_backlog.", len_delivered_events
            )

        logger.info("Runner shut down complete.")

    async def _process_sent_events(self, batch: list[LogEvent]) -> list[LogEvent]:
        """Process a batch of events got from sender iterator."""

        logger.debug("Got batch of events from sender (batch_size=%d).", len(batch))
        for event in batch:
            if event is None:
                continue

            if event.state == EventStateType.FAILED:
                logger.error("event failed: %s", event)
            else:
                logger.debug("event processed: %s", event.state)

        return batch
