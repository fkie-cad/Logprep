"""Pipeline module for processing events through a series of processors."""

import multiprocessing as mp
from collections.abc import Iterator
from itertools import islice

from logprep.factory import Factory
from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

_CONSUME_ENDLESS = True

# --- Globals for worker context ---
_PROCESSORS: list[Processor] | None = None


def _init_worker(processor_configs: list[dict]):
    """Build processors once per worker from their config."""
    global _PROCESSORS
    _PROCESSORS = []
    for cfg in processor_configs:
        proc = Factory.create(cfg)
        proc.setup()
        _PROCESSORS.append(proc)


def _process_event_in_worker(event: LogEvent) -> LogEvent:
    """Process a single event using global processors in this worker."""
    global _PROCESSORS
    event.state.next_state()
    for processor in _PROCESSORS:
        if not event.data:
            break
        processor.process(event)
    if not event.errors:
        event.state.next_state(success=True)
    else:
        event.state.next_state(success=False)
    return event


class Pipeline(Iterator):
    """Pipeline class to process events through a series of processors.

    The `use_multiprocessing` flag controls whether events are processed in parallel
    using Python's multiprocessing module with the "spawn" start method.

        False: Single-threaded mode (sequential processing, useful for debugging)
        True: Multiprocessing mode using "spawn" for process creation (default)
    """

    def __init__(
        self,
        input_connector: Iterator[LogEvent],
        processors: list[Processor],
        process_count: int = 10,
        use_multiprocessing: bool = True,
    ) -> None:
        self._input = input_connector
        self._processors = processors
        self._process_count = process_count
        self._use_mp = use_multiprocessing

        if self._use_mp:
            mp.set_start_method("spawn", force=True)
            self._ctx = mp.get_context("spawn")
            # Store picklable configs instead of processor objects
            self._processor_configs = [p._config for p in processors]
        else:
            self._ctx = None

    def __iter__(self):
        if self._use_mp:
            with self._ctx.Pool(
                processes=self._process_count,
                initializer=_init_worker,
                initargs=(self._processor_configs,),
            ) as pool:
                while _CONSUME_ENDLESS:
                    events = (e for e in self._input if e is not None and e.data)
                    batch = list(islice(events, self._process_count))
                    if not batch:
                        break
                    yield from pool.map(_process_event_in_worker, batch)
        else:
            while _CONSUME_ENDLESS:
                events = (e for e in self._input if e is not None and e.data)
                batch = list(islice(events, self._process_count))
                if not batch:
                    break
                for event in batch:
                    yield self._process_event_single(event)

    def __next__(self):
        """
        Return the next processed event or None if no valid event is found.
        """
        try:
            while (next_event := next(self._input)) is None or not next_event.data:
                continue
        except StopIteration:
            return None
        return self._process_event_single(next_event)

    def _process_event_single(self, event: LogEvent) -> LogEvent:
        """Single-process event processing."""
        event.state.next_state()
        for processor in self._processors:
            if not event.data:
                break
            processor.process(event)
        if not event.errors:
            event.state.next_state(success=True)
        else:
            event.state.next_state(success=False)
        return event
