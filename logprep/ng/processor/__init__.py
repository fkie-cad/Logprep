from collections.abc import Sequence

from logprep.ng.abc.event import LogEvent
from logprep.ng.abc.processor import Processor


# TODO add measure_time like in non-ng
async def process(event: LogEvent, processors: Sequence[Processor]) -> LogEvent:
    for processor in processors:
        if not event.data or event.errors:
            break
        await processor.process(event)
    return event
