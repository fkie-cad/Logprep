"""pipeline module for processing events through a series of processors."""

import logging

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

logger = logging.getLogger("Pipeline")


def _process_event(event: LogEvent | None, processors: list[Processor]) -> LogEvent:
    """process all processors for one event"""
    if event is None or not event.data:
        raise ValueError("no event given")
    event.state.next_state()
    for processor in processors:
        if not event.data:
            break
        processor.process(event)
    if not event.errors:
        event.state.next_state(success=True)
    else:
        event.state.next_state(success=False)
        logger.error("event failed: %s with errors: %s", event, event.errors)
    return event


class Pipeline:
    """Pipeline class to process events through a series of processors."""

    def __init__(
        self,
        processors: list[Processor],
    ) -> None:
        self.processors = processors

    def process(self, event: LogEvent) -> LogEvent:
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
        return _process_event(event, processors=self.processors)

    def shut_down(self) -> None:
        """Shutdown the pipeline gracefully."""

        for processor in self.processors:
            processor.shut_down()

        logger.info("All processors has been shut down.")
        logger.info("Pipeline has been shut down.")

    def setup(self) -> None:
        """Setup the pipeline components."""

        for processor in self.processors:
            processor.setup()

        logger.info("Pipeline has been set up.")
