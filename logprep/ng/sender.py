from collections.abc import Iterator
from itertools import islice
from typing import Generator

from logprep.ng.abc.event import ExtraDataEvent
from logprep.ng.abc.output import Output
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline


class Sender(Iterator):
    def __init__(self, pipeline: Pipeline, outputs: list[Output], error_output: Output) -> None:
        self._pipeline = pipeline
        self._outputs = {output.name: output for output in outputs}
        self._default_outputs = {output.name: output for output in outputs if output.default}
        self._error_output = error_output

    def __next__(self):
        event = next(self._pipeline)
        self._send(event)

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""
        while True:
            events = (event for event in self._pipeline if event is not None and event.data)
            batch = list(islice(events, self._pipeline._process_count))
            if not batch:
                break
            yield from map(self._send, batch)

    def _send_extra_data(self, event: LogEvent) -> None:
        extra_datas: list[ExtraDataEvent] = event.extra_data
        for extra_data in extra_datas:
            for output in extra_data.outputs:
                for output_name, output_target in output.items():
                    if output_name in self._outputs:
                        self._outputs[output_name].store_custom(extra_data, output_target)
                    else:
                        raise ValueError(f"Output {output_name} not configured.")

    def _send(self, event: LogEvent) -> LogEvent:
        if event.extra_data:
            self._send_extra_data(event)
        if event.state.current_state == EventStateType.PROCESSED:
            for _, output in self._default_outputs.items():
                output.store(event)
        elif event.state.current_state == EventStateType.FAILED and self._error_output:
            self._error_output.store(event)
        return event
