"""
Runner module
"""

import asyncio
import logging
import typing
from collections import defaultdict
from collections.abc import Sequence

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.event import ExtraDataEvent
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor import process
from logprep.ng.util.async_helpers import raise_from_gather
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


class InvalidOutput(LogprepException):
    """Referenced output does not exist"""

    def __init__(self, output_name, *args, **kwargs):
        super().__init__(f"Output {output_name} not configured.", *args, **kwargs)


def create_orchestrator(
    input_source: Input,
    processors: Sequence[Processor],
    default_output: Output,
    named_outputs: dict[str, Output],
    error_output: Output | None,
) -> WorkerOrchestrator:  # pylint: disable=too-many-locals
    """
    Creates an worker orchestrator representing the core pipeline workflow.
    """
    process_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
    send_to_default_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
    send_to_extras_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
    send_to_error_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)
    acknowledge_queue = SizeLimitedQueue[LogEvent](maxsize=MAX_QUEUE_SIZE)

    async def transfer_batch(batch: list[LogEvent]) -> None:
        batch = [e for e in batch if e is not None]

        for event in batch:
            await process_queue.put(event)

    input_worker: Worker[LogEvent, LogEvent] = Worker(
        name="input_worker",
        batch_size=500,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=input_source,
        out_queues=[process_queue],
        handler=transfer_batch,
    )

    async def _processor_handler(batch: list[LogEvent]) -> None:
        async def _handle(event: LogEvent):
            processed_event = await process(event, processors)

            if not processed_event.errors:
                if processed_event.extra_data:
                    await send_to_extras_queue.put(processed_event)
                else:
                    await send_to_default_queue.put(processed_event)
            else:
                await send_to_error_queue.put(processed_event)

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
            output_name: defaultdict(list) for output_name in named_outputs.keys()
        }

        for event in batch:
            for extra in typing.cast(Sequence[ExtraDataEvent], event.extra_data):
                for out in extra.outputs:
                    try:
                        output_buffers[out.output_name][out.output_target].append(extra)
                    except KeyError:
                        extra.errors.append(InvalidOutput(out.output_name))

        raise_from_gather(
            await asyncio.gather(
                *(
                    named_outputs[name].store_batch(events, target)
                    for name, target_events in output_buffers.items()
                    for target, events in target_events.items()
                ),
                return_exceptions=True,
            ),
            message="critical failure while sending extra events",
        )

        for event in batch:
            if any(extra.errors for extra in event.extra_data):
                # TODO create higher order exception in event itself?
                await send_to_error_queue.put(event)
            else:
                await send_to_default_queue.put(event)

    extra_output_worker: Worker[LogEvent, LogEvent] = Worker(
        name="extra_output_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=send_to_extras_queue,
        out_queues=[send_to_default_queue, send_to_error_queue],
        handler=_send_extras_handler,
    )

    async def _send_default_output_handler(batch: list[LogEvent]):
        await default_output.store_batch(batch)

        for event in batch:
            if event.errors:
                await send_to_error_queue.put(event)
            else:
                await acknowledge_queue.put(event)

    output_worker: Worker[LogEvent, LogEvent] = Worker(
        name="output_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=send_to_default_queue,
        out_queues=[acknowledge_queue, send_to_error_queue],
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

        # TODO split in two handler functions and select right handler only once
        if error_output is not None:
            error_events = await error_output.store_batch(list(map(_to_error, batch)))

            for error_event in error_events:
                if not error_event.errors:
                    # TODO use generic type parameter for outputs?
                    await acknowledge_queue.put(typing.cast(ErrorEvent, error_event).parent)
                else:
                    # TODO more sophisticated error handling
                    raise RuntimeError("error output failed to send event")
        else:
            for event in batch:
                await acknowledge_queue.put(event)

    error_worker: Worker[LogEvent, LogEvent] = Worker(
        name="error_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=send_to_error_queue,
        out_queues=[acknowledge_queue],
        handler=_send_error_output_handler,
    )

    acknowledge_worker: Worker[LogEvent, LogEvent] = Worker(
        name="acknowledge_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=acknowledge_queue,
        out_queues=[],
        handler=input_source.acknowledge,
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
