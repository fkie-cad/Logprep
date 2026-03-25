"""
Runner module
"""

import asyncio
import logging
import typing
from asyncio import CancelledError
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
from logprep.ng.util.events import partition_by_state
from logprep.ng.util.worker.types import SizeLimitedQueue
from logprep.ng.util.worker.worker import Worker, WorkerOrchestrator

logger = logging.getLogger("PipelineManager")  # pylint: disable=no-member


BATCH_SIZE = 2_500
BATCH_INTERVAL_S = 5
MAX_QUEUE_SIZE = BATCH_SIZE


class PipelineManager:
    """Orchestrator class managing pipeline inputs, processors and outputs"""

    def __init__(self, configuration: Configuration, shutdown_timeout_s: float) -> None:
        """Initialize the component from the given `configuration`."""

        self.configuration = configuration
        self._shutdown_timeout_s = shutdown_timeout_s

    async def setup(self):
        """Setup the pipeline manager."""

        self._event_backlog = SetEventBacklog()

        self._input_connector = cast(Input, Factory.create(self.configuration.input))
        await self._input_connector.setup()

        processors = [
            typing.cast(Processor, Factory.create(processor_config))
            for processor_config in self.configuration.pipeline
        ]
        for processor in processors:
            await processor.setup()

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
        await self._sender.setup()

        self._queues = []
        self._orchestrator = self._create_orchestrator()

    def _create_orchestrator(self) -> WorkerOrchestrator:  # pylint: disable=too-many-locals
        process_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
        send_to_default_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
        send_to_extras_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
        send_to_error_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
        acknowledge_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
        self._queues = [
            process_queue,
            send_to_default_queue,
            send_to_extras_queue,
            send_to_error_queue,
            acknowledge_queue,
        ]

        async def transfer_batch(batch: list[LogEvent]) -> list[LogEvent]:
            for event in batch:
                event.state.current_state = EventStateType.RECEIVED

            return batch

        input_worker: Worker[LogEvent, LogEvent] = Worker(
            name="input_worker",
            batch_size=500,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=self._input_connector(timeout=self.configuration.timeout),
            out_queue=process_queue,
            handler=transfer_batch,
        )

        async def _processor_handler(batch: list[LogEvent]) -> list[LogEvent]:
            async def _handle(event: LogEvent):
                # TODO make processing async
                self._pipeline.process(event)
                # TODO handle all possible states
                if event.state != EventStateType.FAILED:
                    if event.extra_data:
                        await send_to_extras_queue.put(event)
                    else:
                        await send_to_default_queue.put(event)
                else:
                    await send_to_error_queue.put(event)

            await asyncio.gather(*map(_handle, batch))
            return batch

        processing_worker: Worker[LogEvent, LogEvent] = Worker(
            name="processing_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=process_queue,
            handler=_processor_handler,
        )

        async def _send_extras_handler(batch: list[LogEvent]) -> list[LogEvent]:
            return await self._sender.send_extras(batch)

        extra_output_worker: Worker[LogEvent, LogEvent] = Worker(
            name="extra_output_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_extras_queue,
            out_queue=send_to_default_queue,
            handler=_send_extras_handler,
        )

        async def _send_default_output_handler(batch: list[LogEvent]) -> list[LogEvent]:
            return await self._sender.send_default_output(batch)

        output_worker: Worker[LogEvent, LogEvent] = Worker(
            name="output_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_default_queue,
            out_queue=acknowledge_queue,
            handler=_send_default_output_handler,
        )

        async def _report_event_state(batch: list[LogEvent]) -> list[LogEvent]:
            events_by_state = partition_by_state(batch)
            logger.info(
                "Finished processing %d events: %s",
                len(batch),
                ", ".join(f"#{state}={len(events)}" for state, events in events_by_state.items()),
            )
            return batch

        error_worker: Worker[LogEvent, LogEvent] = Worker(
            name="error_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_error_queue,
            # TODO implement handling and sending failed events
            handler=_report_event_state,
        )

        acknowledge_worker: Worker[LogEvent, LogEvent] = Worker(
            name="acknowledge_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=acknowledge_queue,
            handler=_report_event_state,
        )

        return WorkerOrchestrator(
            workers=[
                input_worker,
                processing_worker,
                extra_output_worker,
                output_worker,
                error_worker,
                acknowledge_worker,
            ]
        )

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""

        try:
            await self._orchestrator.run()
        except CancelledError:
            logger.debug("PipelineManager.run cancelled. Shutting down.")
            await self._shut_down()
            raise
        except Exception:
            logger.exception("PipelineManager.run failed. Shutting down.")
            await self._shut_down()
            raise

    async def _shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        logger.debug(
            "Remaining items in queues: [%s]", ", ".join(f"{q.qsize()}" for q in self._queues)
        )

        if self._orchestrator is not None:
            # TODO only a fraction of shutdown_timeout_s should be passed to the orchestrator
            await self._orchestrator.shut_down(self._shutdown_timeout_s)

        logger.debug(
            "Remaining items in queues: [%s]", ", ".join(f"{q.qsize()}" for q in self._queues)
        )

        if self._sender is not None:
            await self._sender.shut_down()
        # self._input_connector.acknowledge()

        len_delivered_events = len(list(self._event_backlog.get(EventStateType.DELIVERED)))
        if len_delivered_events:
            logger.error(
                "Input connector has %d non-acked events in event_backlog.", len_delivered_events
            )

        logger.info("Runner shut down complete.")
