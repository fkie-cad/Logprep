"""
Runner module
"""

import asyncio
import logging
import typing
from asyncio import CancelledError
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

from logprep.factory import Factory
from logprep.ng.abc.component import NgComponent
from logprep.ng.abc.event import ExtraDataEvent
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.worker.types import SizeLimitedQueue
from logprep.ng.util.worker.worker import Worker, WorkerOrchestrator

logger = logging.getLogger("PipelineManager")


BATCH_SIZE = 1000
BATCH_INTERVAL_S = 5
MAX_QUEUE_SIZE = BATCH_SIZE


class LogprepExceptionGroup(ExceptionGroup):
    """Custom ExceptionGroup for Logprep exceptions to override the default
    string representation."""

    def __str__(self) -> str:
        return f"{self.message}: {self.exceptions}"


class PipelineManager:
    """Orchestrator class managing pipeline inputs, processors and outputs"""

    def __init__(self, configuration: Configuration, shutdown_timeout_s: float) -> None:
        """Initialize the component from the given `configuration`."""

        self.configuration = configuration
        self._shutdown_timeout_s = shutdown_timeout_s

    async def setup(self) -> None:
        """Setup the pipeline manager."""

        self._components: list[NgComponent] = []

        self._input_connector = cast(Input, Factory.create(self.configuration.input))
        self._components.append(self._input_connector)

        processors = [
            cast(Processor, Factory.create(processor_config))
            for processor_config in self.configuration.pipeline
        ]
        self._components.extend(processors)

        self._pipeline = Pipeline(processors)

        self._outputs = {
            output_name: cast(Output, Factory.create({output_name: output}))
            for output_name, output in self.configuration.output.items()
        }
        self._components.extend(self._outputs.values())

        # there must always be one!
        self._default_output = [output for output in self._outputs.values() if output.default][0]

        self._error_output = (
            cast(Output, Factory.create(self.configuration.error_output))
            if self.configuration.error_output
            else None
        )

        if self._error_output is not None:
            self._components.append(self._error_output)
        else:
            logger.warning("No error output configured.")

        await asyncio.gather(*(component.setup() for component in self._components))

        self._queues: list[SizeLimitedQueue] = []
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

        async def transfer_batch(batch: list[LogEvent]) -> None:
            batch = [e for e in batch if e is not None]

            for event in batch:
                await process_queue.put(event)

        input_worker: Worker[LogEvent, LogEvent] = Worker(
            name="input_worker",
            batch_size=500,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=self._input_connector(timeout=self.configuration.timeout),
            out_queues=[process_queue],
            handler=transfer_batch,
        )

        async def _processor_handler(batch: list[LogEvent]) -> None:
            async def _handle(event: LogEvent):
                await self._pipeline.process(event)
                if not event.errors:
                    if event.extra_data:
                        await send_to_extras_queue.put(event)
                    else:
                        await send_to_default_queue.put(event)
                else:
                    await send_to_error_queue.put(event)

            await asyncio.gather(*map(_handle, batch))

        processing_worker: Worker[LogEvent, LogEvent] = Worker(
            name="processing_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=process_queue,
            out_queues=[send_to_extras_queue, send_to_default_queue, send_to_error_queue],
            handler=_processor_handler,
        )

        async def _send_extras_handler(batch: list[LogEvent]) -> None:
            output_buffers: dict[str, dict[str, list[ExtraDataEvent]]] = {
                output_name: defaultdict(list) for output_name in self._outputs.keys()
            }

            for event in batch:
                for extra in typing.cast(Sequence[ExtraDataEvent], event.extra_data):
                    for out in extra.outputs:
                        try:
                            output_buffers[out.output_name][out.output_target].append(extra)
                        except KeyError as error:
                            raise ValueError(f"Output {out.output_name} not configured.") from error

            results = await asyncio.gather(
                *(
                    self._outputs[name].store_batch(events, target)
                    for name, target_events in output_buffers.items()
                    for target, events in target_events.items()
                ),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.exception("Error while sending processed event", exc_info=r)
            # TODO implement error handling

            logger.debug("return send_extras %d", len(batch))

            # extra events are assumed to be sent successfully, primary events can now be sent
            for event in batch:
                await send_to_default_queue.put(event)

        extra_output_worker: Worker[LogEvent, LogEvent] = Worker(
            name="extra_output_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_extras_queue,
            out_queues=[send_to_default_queue],
            handler=_send_extras_handler,
        )

        async def _send_default_output_handler(batch: list[LogEvent]):
            await self._default_output.store_batch(batch)

        output_worker: Worker[LogEvent, LogEvent] = Worker(
            name="output_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_default_queue,
            out_queues=[acknowledge_queue],
            handler=_send_default_output_handler,
        )

        async def _send_error_output_handler(batch: list[LogEvent]) -> None:
            def _to_error(event: LogEvent) -> ErrorEvent:
                reason = (
                    LogprepExceptionGroup("Error during processing", event.errors)
                    if event.errors
                    else Exception("Unknown error")
                )
                return ErrorEvent(log_event=event, reason=reason, state=EventStateType.PROCESSED)

            if self._error_output is not None:
                await self._error_output.store_batch(list(map(_to_error, batch)))
            # TODO handle error events which failed to be sent
            # logger.error("Error during sending to error output: %s", error_event)

            for event in batch:
                await acknowledge_queue.put(event)

        error_worker: Worker[LogEvent, LogEvent] = Worker(
            name="error_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=send_to_error_queue,
            out_queues=[],
            handler=_send_error_output_handler,
        )

        acknowledge_worker: Worker[LogEvent, LogEvent] = Worker(
            name="acknowledge_worker",
            batch_size=BATCH_SIZE,
            batch_interval_s=BATCH_INTERVAL_S,
            in_queue=acknowledge_queue,
            out_queues=[],
            handler=self._input_connector.acknowledge,
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

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run the runner and continuously process events until stopped."""

        try:
            await self._orchestrator.run(stop_event, self._shutdown_timeout_s)
        except (CancelledError, Exception):
            logger.error("PipelineManager.run cancelled or failed; shutting down...", exc_info=True)
            await self._shut_down()
            raise
        await self._shut_down()

    async def _shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        await asyncio.gather(*(component.shut_down() for component in self._components))

        # TODO: acknowledge queue is the last queue
        len_delivered_events = self._queues[-1].qsize()
        if len_delivered_events:
            logger.error(
                "Input connector has %d non-acked events in the queue.", len_delivered_events
            )

        logger.info("Manager shut down complete.")
