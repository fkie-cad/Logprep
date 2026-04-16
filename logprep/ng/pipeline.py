"""pipeline module for processing events through a series of processors."""

import asyncio
import logging

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("Pipeline")


async def _process_event(event: LogEvent, processors: list[Processor]) -> LogEvent:
    """process all processors for one event"""
    for processor in processors:
        if not event.data:
            break
        await processor.process(event)
    return event


class Pipeline:
    """Pipeline class to process events through a series of processors."""

    def __init__(
        self,
        processors: list[Processor],
    ) -> None:
        self.processors = processors

    async def process(self, event: LogEvent) -> LogEvent:
        """Process the given event through the series of configured processors

        Parameters
        ----------
        event : LogEvent
            The event to be processed and modified in-place.

        Returns
        -------
        LogEvent
            The event which was presented as an input and modified in-place.
        """
        return await _process_event(event, processors=self.processors)

    async def shut_down(self) -> None:
        """Shutdown the pipeline gracefully."""

        for processor in self.processors:
            await processor.shut_down()

        logger.info("All processors has been shut down.")
        logger.info("Pipeline has been shut down.")

    async def setup(self) -> None:
        """Setup the pipeline components."""

        await asyncio.gather(
            *(processor.setup() for processor in self.processors), return_exceptions=True
        )

        logger.info("Pipeline has been set up.")
