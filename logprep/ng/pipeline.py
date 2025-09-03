"""Pipeline module for processing events through a series of processors."""

import multiprocessing as mp
import os
import traceback
from collections.abc import Iterator
from itertools import islice
from typing import Generator

import attrs

from logprep.factory import Factory
from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent

_CONSUME_ENDLESS = True
_PROCESSORS: list[Processor] | None = None


def _initialize_processors_for_mp(processor_configs: list[dict]) -> None:
    """Initialize processors for use in multiprocessing workers."""

    global _PROCESSORS

    if _PROCESSORS is not None:
        return

    _PROCESSORS = [Factory.create(configuration={name: cfg}) for (name, cfg) in processor_configs]


def _mp_process_event(event: LogEvent) -> LogEvent:
    """Multiprocessing-safe processing of a single event using global _PROCESSORS."""

    try:
        event.state.next_state()
        for processor in _PROCESSORS:
            if not event.data:
                break
            processor.process(event)
        event.state.next_state(success=not event.errors)
        return event
    except Exception as e:
        msg = f"[Worker PID {os.getpid()}] Exception:\n{traceback.format_exc()}\n"
        os.write(2, msg.encode())
        raise e


class Pipeline(Iterator):
    """Pipeline class to process events through a series of processors.
        use_multiprocessing : bool, default=True
        Controls whether events are processed sequentially (False)
        or in parallel using Python's multiprocessing module with the
        "spawn" start method (True).

    Parameters
    ----------
    input_connector : Iterator[LogEvent]
        Source iterator providing the input events.
    processors : list[Processor]
        List of processors applied to each event in sequence.
    process_count : int, default=10
        - If `use_multiprocessing` is False:
          Defines the batch size of events processed in one iteration step.
        - If `use_multiprocessing` is True:
          Defines the number of worker processes spawned for parallel processing.
    use_multiprocessing : bool, default=False
        Controls whether events are processed sequentially (False)
        or in parallel using Python's multiprocessing module with the
        "spawn" start method (True).

    Examples:
        >>> from logprep.ng.event.log_event import LogEvent
        >>> from logprep.ng.abc.event import Event
        >>> class MockProcessor:
        ...     def process(self, event: LogEvent) -> None:
        ...         event.data["processed"] = True
        ...
        >>>
        >>> # Create test events
        >>> events = [
        ...     LogEvent({"message": "test1"}, original=b""),
        ...     LogEvent({"message": "test2"}, original=b"")
        ... ]
        >>> processors = [MockProcessor()]
        >>>
        >>> # Create and run pipeline
        >>> pipeline = Pipeline(iter(events), processors)
        >>> processed_events = list(pipeline)
        >>> len(processed_events)
        2
        >>> processed_events[0].data["processed"]
        True
        >>> processed_events[1].data["message"]
        'test2'
    """

    def __init__(
        self,
        input_connector: Iterator[LogEvent],
        processors: list[Processor],
        process_count: int = 10,
        use_multiprocessing: bool = False,
    ) -> None:
        self._input = input_connector
        self._processors = processors
        self._process_count = process_count

        self._use_mp = use_multiprocessing
        self._ctx = None
        self._pool = None
        self._processor_configs = None

        if self._use_mp:
            if not mp.get_start_method(allow_none=True):
                mp.set_start_method("spawn", force=True)

            self._ctx = mp.get_context("spawn")
            self._processor_configs = [
                (processor.name, attrs.asdict(processor._config)) for processor in processors
            ]
            self._pool = self._ensure_pool()

    def _ensure_pool(self):
        """Create (lazily) and cache a Pool for __next__ calls."""

        if self._pool is None:
            self._pool = self._ctx.Pool(
                processes=self._process_count,
                initializer=_initialize_processors_for_mp,
                initargs=(self._processor_configs,),
            )

        return self._pool

    def shut_down(self) -> None:
        """Close & join the cached Pool if it exists."""
        if self._pool is not None:
            try:
                self._pool.close()
                self._pool.join()
            finally:
                self._pool = None

    def __iter__(self) -> Generator[LogEvent, None, None]:
        """Iterate over processed events."""

        if self._use_mp:
            while _CONSUME_ENDLESS:
                events = (event for event in self._input if event is not None and event.data)
                batch = list(islice(events, self._process_count))
                if not batch:
                    break
                yield from self._pool.map(_mp_process_event, batch)
        else:
            while _CONSUME_ENDLESS:
                events = (event for event in self._input if event is not None and event.data)
                batch = list(islice(events, self._process_count))
                if not batch:
                    break
                yield from map(self._process_event, batch)

    def __next__(self):
        """
        Return the next processed event or None if no valid event is found.
        This method intentionally deviates from the standard Python iterator protocol.
        Normally, __next__() must raise StopIteration to signal that there are no more
        items. In this Pipeline, __next__() instead returns None when no valid event
        is available. This design allows callers to check for "no event" without
        handling StopIteration explicitly, but means the method is not strictly
        iterator-compliant by design.
        """
        try:
            while (next_event := next(self._input)) is None or not next_event.data:
                continue
        except StopIteration:
            return None

        if self._use_mp:
            return self._pool.map(_mp_process_event, [next_event])[0]
        else:
            return self._process_event(next_event)

    def _process_event(self, event: LogEvent) -> LogEvent:
        """process all processors for one event"""

        event.state.next_state()
        for processor in self._processors:
            if not event.data:
                break
            processor.process(event)
        event.state.next_state(success=not event.errors)
        return event
