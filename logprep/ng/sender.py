"""sender module"""

import asyncio
import logging
import typing
from collections import defaultdict
from collections.abc import Sequence

from logprep.ng.abc.event import ExtraDataEvent
from logprep.ng.abc.output import Output
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("Sender")


class LogprepExceptionGroup(ExceptionGroup):
    """Custom ExceptionGroup for Logprep exceptions to override the default
    string representation."""

    def __str__(self) -> str:
        return f"{self.message}: {self.exceptions}"


class Sender:
    """Sender class to handle sending events to configured outputs."""

    def __init__(
        self,
        outputs: list[Output],
        error_output: Output | None = None,
    ) -> None:
        self._outputs = {output.name: output for output in outputs}
        self._default_output = [output for output in outputs if output.default][0]
        self._error_output = error_output

    async def send_extras(self, batch_events: Sequence[LogEvent]) -> Sequence[LogEvent]:
        output_buffers: dict[str, dict[str, list[ExtraDataEvent]]] = {
            output_name: defaultdict(list) for output_name in self._outputs.keys()
        }

        for event in batch_events:
            for extra in typing.cast(Sequence[ExtraDataEvent], event.extra_data):
                for output in extra.outputs:
                    for name, target in output.items():
                        try:
                            output_buffers[name][target].append(extra)
                        except KeyError as error:
                            raise ValueError(f"Output {name} not configured.") from error

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

        # TODO: filter and handle successful + failed
        # succeed_events, failed_events = (
        #    [e for e in batch_events if e.state == EventStateType.DELIVERED],
        #    [e for e in batch_events if e.state == EventStateType.FAILED],
        # )
        # assert len(succeed_events) + len(failed_events) == len(batch_events), "Lost events in batch"

        logger.debug("return send_extras %d", len(batch_events))

        return batch_events

    async def send_default_output(self, batch_events: Sequence[LogEvent]) -> Sequence[LogEvent]:
        logger.debug("send_default_output %d", len(batch_events))
        return await self._default_output.store_batch(batch_events)  # type: ignore

    async def _send_and_flush_failed_events(self, batch_events: list[LogEvent]) -> None:
        # send in parallel (minimal change vs. serial list comprehension)
        error_events = await asyncio.gather(*(self._send_failed(event) for event in batch_events))

        await self._error_output.flush()  # type: ignore[union-attr]

        failed_error_events = [
            event for event in error_events if event.state is EventStateType.FAILED
        ]
        for error_event in failed_error_events:
            logger.error("Error during sending to error output: %s", error_event)

    async def _send_failed(self, event: LogEvent) -> ErrorEvent:
        """Send the event to the error output.
        If event can't be sent, it will be logged as an error.
        """
        error_event = self._get_error_event(event)
        await self._error_output.store(error_event)  # type: ignore[union-attr]
        return error_event

    def _get_error_event(self, event: LogEvent) -> ErrorEvent:
        """returns an ErrorEvent instance based on the provided LogEvent.
        The state of the ErrorEvent is set to PROCESSED
        """
        reason = (
            LogprepExceptionGroup("Error during processing", event.errors)
            if event.errors
            else Exception("Unknown error")
        )
        return ErrorEvent(log_event=event, reason=reason, state=EventStateType.PROCESSED)

    async def shut_down(self) -> None:
        """Shutdown all outputs gracefully."""
        for _, output in self._outputs.items():
            await output.shut_down()
        if self._error_output:
            await self._error_output.shut_down()
        logger.info("All outputs have been shut down.")
        logger.info("Sender has been shut down.")

    async def setup(self) -> None:
        """Setup all outputs."""
        for _, output in self._outputs.items():
            await output.setup()
        if self._error_output:
            await self._error_output.setup()
        logger.info("All outputs have been set up.")
