from collections.abc import Sequence

from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent


async def process(event: LogEvent, processors: Sequence[Processor]) -> LogEvent:
    for processor in processors:
        if not event.data or event.errors:
            break
        await processor.process(event)
    return event
