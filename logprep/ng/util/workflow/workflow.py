"""
Runner module
"""

import asyncio
import itertools
import logging
import typing
from collections.abc import Sequence

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.event import (
    AcknowledgableEvent,
    ErrorEvent,
    ExtraDataEvent,
    LogEvent,
)
from logprep.ng.abc.input import Input, InputError, InputWarning
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.processor import process
from logprep.ng.util.async_helpers import raise_from_gather
from logprep.ng.util.errors import ExtraEventDeliveryFailure
from logprep.ng.util.workflow.config import WorkflowConfig
from logprep.ng.util.workflow.worker import (
    BatchingWorker,
    SequentialWorker,
    SizeLimitedQueue,
    Worker,
    WorkerOrchestrator,
)

logger = logging.getLogger("PipelineManager")


class InvalidOutput(LogprepException):
    """Referenced output does not exist"""

    def __init__(self, output_name, *args, **kwargs):
        super().__init__(f"Output {output_name} not configured.", *args, **kwargs)


def create_orchestrator(
    input_source: Input,
    processors: Sequence[Processor],
    default_output: Output | None,
    named_outputs: dict[str, Output],
    error_output: Output | None,
    config: WorkflowConfig,
) -> WorkerOrchestrator:  # pylint: disable=too-many-locals
    """
    Creates an worker orchestrator representing the core pipeline workflow.
    """
    process_queue = SizeLimitedQueue[LogEvent](
        maxsize=config.workers["processing_worker"].queue_size
    )
    send_to_default_queue = SizeLimitedQueue[LogEvent](
        maxsize=config.workers["output_worker"].queue_size
    )
    send_to_extras_queue = SizeLimitedQueue[LogEvent](
        maxsize=config.workers["extra_output_worker"].queue_size
    )
    send_to_error_queue = SizeLimitedQueue[ErrorEvent](
        maxsize=config.workers["error_worker"].queue_size
    )
    acknowledge_queue = SizeLimitedQueue[AcknowledgableEvent](
        maxsize=config.workers["acknowledge_worker"].queue_size
    )

    async def _distribute_input(event: LogEvent | ErrorEvent | None) -> None:
        match event:
            case None:
                return
            case LogEvent():
                await process_queue.put(event)
            case ErrorEvent():
                await send_to_error_queue.put(event)

    input_worker: Worker[LogEvent | ErrorEvent | None] = SequentialWorker(
        name="input_worker",
        in_queue=input_source,
        out_queues=[process_queue, send_to_error_queue],
        handler=_distribute_input,
    )

    async def _processor_handler(batch: Sequence[LogEvent]) -> None:
        # TODO use sync pipeline as long as processors are not truly async
        for i, event in enumerate(batch):
            try:
                await process(event, processors)
            except Exception as exc:
                logger.error("unexpected error during event processing", exc_info=True)
                if not event.is_failed():
                    event.mark_failed(exc)

            if not event.errors:
                if event.extra_data:
                    await send_to_extras_queue.put(event)
                else:
                    await send_to_default_queue.put(event)
            else:
                await send_to_error_queue.put(ErrorEvent.from_failed_event(event))

            if i % 50 == 0:
                await asyncio.sleep(0)

    processing_worker: Worker[LogEvent] = BatchingWorker(
        name="processing_worker",
        in_queue=process_queue,
        out_queues=[send_to_extras_queue, send_to_default_queue, send_to_error_queue],
        handler=_processor_handler,
        config=config.workers["processing_worker"],
    )

    async def _send_extras_handler(batch: Sequence[LogEvent]) -> None:
        extra_events = list(itertools.chain.from_iterable(event.extra_data for event in batch))

        output_name_to_extra_events: dict[str, list[ExtraDataEvent]] = {
            output_name: [] for output_name in named_outputs.keys()
        }

        for extra in extra_events:
            if extra.output_name is None:
                if default_output:
                    output_name_to_extra_events[default_output.name].append(extra)
            else:
                try:
                    output_name_to_extra_events[extra.output_name].append(extra)
                except KeyError:
                    extra.mark_failed(InvalidOutput(extra.output_name))

        raise_from_gather(
            await asyncio.gather(
                *(
                    named_outputs[name].store(events)
                    for name, events in output_name_to_extra_events.items()
                    if events
                ),
                return_exceptions=True,
            ),
            message="critical failure while sending extra events",
        )

        for event in batch:
            if any(extra.errors for extra in event.extra_data):
                event.mark_failed(ExtraEventDeliveryFailure.from_event(event))
                await send_to_error_queue.put(ErrorEvent.from_failed_event(event))
            else:
                await send_to_default_queue.put(event)

    extra_output_worker: Worker[LogEvent] = BatchingWorker(
        name="extra_output_worker",
        config=config.workers["extra_output_worker"],
        in_queue=send_to_extras_queue,
        out_queues=[send_to_default_queue, send_to_error_queue],
        handler=_send_extras_handler,
    )

    async def _send_default_output_handler(batch: Sequence[LogEvent]):
        if default_output:
            await default_output.store(batch)
            logger.debug("Stored output in %s", default_output.name)

        for event in batch:
            if event.errors:
                await send_to_error_queue.put(ErrorEvent.from_failed_event(event))
            elif event.input_meta is not None:
                await acknowledge_queue.put(event)

    output_worker: Worker[LogEvent] = BatchingWorker(
        name="output_worker",
        config=config.workers["output_worker"],
        in_queue=send_to_default_queue,
        out_queues=[acknowledge_queue, send_to_error_queue],
        handler=_send_default_output_handler,
    )

    async def _send_error_output_handler(batch: Sequence[ErrorEvent]) -> None:
        to_acknowledge: Sequence[ErrorEvent] = batch

        if error_output is not None:
            # TODO ensure to retry forever for retryable errors
            await error_output.store(batch)

            if any(error_event.is_failed() for error_event in batch):
                to_acknowledge = [error for error in batch if not error.is_failed()]

                # TODO log offsets for messages or fail hard; configurable?
                logger.error(
                    "failed to store %d error events in the error output",
                    len(batch) - len(to_acknowledge),
                )

        for event in to_acknowledge:
            if event.input_meta is not None:
                # TODO runtime_checkable is not performant; find a better way
                await acknowledge_queue.put(typing.cast(AcknowledgableEvent, event))
            else:
                logger.debug("not acknowleding event")

    error_worker: Worker[ErrorEvent] = BatchingWorker(
        name="error_worker",
        config=config.workers["error_worker"],
        in_queue=send_to_error_queue,
        out_queues=[acknowledge_queue],
        handler=_send_error_output_handler,
    )

    async def _acknowledge_events(batch: Sequence[AcknowledgableEvent]) -> None:
        try:
            await input_source.acknowledge(batch)
        except InputWarning as warning:
            logger.warning(str(warning))
        except InputError as error:
            logger.error(error)
            raise error

    acknowledge_worker: Worker[AcknowledgableEvent] = BatchingWorker(
        name="acknowledge_worker",
        config=config.workers["acknowledge_worker"],
        in_queue=acknowledge_queue,
        out_queues=[],
        handler=_acknowledge_events,
    )

    # TODO register a cleanup task to shutdown queues? is this necessary?
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
