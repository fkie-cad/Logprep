"""
Concrete pipeline manager implementation.

This module defines a PipelineManager specialization responsible for
state tracking, backlog management, and runtime metrics. It encapsulates
pipeline-specific processing behavior while preserving the generic
lifecycle and orchestration semantics of the base manager.
"""

import asyncio
import random
import uuid
from asyncio import AbstractEventLoop
from collections import Counter
from typing import Any

from async_pipeline.pipeline_manager import PipelineManager, background_task
from async_pipeline.worker.pipeline_worker import PipelineWorker
from mocked.mocking_functions import commit, store
from mocked.mocking_processor import Processor
from mocked.mocking_types import Event, State


class ConcretePipelineManager(PipelineManager):
    """
    PipelineManager specialization with event state tracking and metrics.

    Maintains an internal backlog for lifecycle/state visibility and
    provides concrete handler implementations for pipeline stages.
    """

    def __init__(
        self,
        workers: list[PipelineWorker[Event]],
        loop: AbstractEventLoop | None = None,
    ) -> None:
        """Initialize backlog storage and runtime metric tracking."""
        super().__init__(workers=workers, loop=loop)

        self._event_backlog: dict[uuid.UUID, Event] = {}
        self._event_backlog_lock = asyncio.Lock()

        self._metric: dict[str, Any] = {
            "start_time": None,
            "last_time": None,
            "last_acked": 0,
            "peak_rate": 0,
            "total_acknowledged": 0,
        }

    async def _update_event_states(
        self,
        events: list[Event],
        new_state: State,
        *,
        locked: bool = False,
    ) -> None:
        """Update state for events, optionally assuming external lock ownership."""
        if locked:
            for event in events:
                event.state = new_state
                self._event_backlog[event.event_id].state = new_state
        else:
            async with self._event_backlog_lock:
                for event in events:
                    event.state = new_state
                    self._event_backlog[event.event_id].state = new_state

    async def handler_input_data(self, events: list[Event]) -> list[Event]:
        """Register incoming events and mark them as received."""
        async with self._event_backlog_lock:
            for event in events:
                self._event_backlog.setdefault(event.event_id, event)

            await self._update_event_states(
                events=events,
                new_state=State.RECEIVED,
                locked=True,
            )

        return events

    async def handler_processor_data(self, events: list[Event]) -> list[Event]:
        """Process events and transition through processing states."""
        await self._update_event_states(events=events, new_state=State.PROCESSING)

        processed_events = await asyncio.to_thread(Processor.process, events)
        # processed_events = Processor.process(events)

        await self._update_event_states(
            events=processed_events,
            new_state=State.PROCESSED,
        )

        return processed_events

    async def handler_output_1_data(self, events: list[Event]) -> list[Event]:
        """Simulate output stage 1 storage."""
        await self._update_event_states(events=events, new_state=State.STORING_OUTPUT_1)

        await asyncio.sleep(random.randint(1, 5) / 10)

        await self._update_event_states(events=events, new_state=State.STORED_OUTPUT_1)

        return events

    async def handler_output_2_data(self, events: list[Event]) -> list[Event]:
        """Simulate output stage 2 storage."""
        await self._update_event_states(events=events, new_state=State.STORING_OUTPUT_2)

        await asyncio.sleep(random.randint(1, 5) / 10)

        await self._update_event_states(events=events, new_state=State.STORED_OUTPUT_2)

        return events

    async def handler_delivery_data(self, events: list[Event]) -> list[Event]:
        """Deliver processed events to the external sink."""
        await self._update_event_states(events=events, new_state=State.DELIVERING)

        await store(events, "output_data")

        await self._update_event_states(events=events, new_state=State.DELIVERED)

        return events

    async def handler_acknowledgement_data(self, events: list[Event]) -> list[Event]:
        """Acknowledge delivered events and update metrics."""
        await self._update_event_states(events=events, new_state=State.ACKNOWLEDGING)

        await commit(events)

        async with self._event_backlog_lock:
            await self._update_event_states(
                events=events,
                new_state=State.ACKNOWLEDGED,
                locked=True,
            )

            self._metric["total_acknowledged"] += len(events)
            total_acked = self._metric["total_acknowledged"]

        self._print_metric(total_acked=total_acked, acked=len(events))
        return events

    def _print_metric(self, total_acked: int, acked: int) -> None:
        """Update and display runtime throughput metrics."""
        now = asyncio.get_running_loop().time()

        if self._metric["start_time"] is None:
            self._metric["start_time"] = now

        elapsed = now - self._metric["start_time"]

        h, rem = divmod(int(elapsed), 3600)
        m, s = divmod(rem, 60)

        elapsed_min = elapsed / 60
        acked_delta = total_acked - self._metric["last_acked"]

        last_time = self._metric["last_time"]
        time_delta = now - last_time if last_time else 0

        live_rate = (acked_delta / time_delta) * 60 if time_delta else 0
        avg_rate = total_acked / elapsed_min if elapsed_min else 0

        self._metric["peak_rate"] = max(self._metric["peak_rate"], live_rate)

        self._metric["last_time"] = now
        self._metric["last_acked"] = total_acked

        print(
            f"Running: {h}h {m}m {s}s | "
            f"Acked: {acked:_} | "
            f"Total Acked: {total_acked:_} | "
            f"Avg Rate: {avg_rate:_.1f}/min | "
            f"Live Rate: {live_rate:_.1f}/min | "
            f"Peak Rate: {self._metric['peak_rate']:_.1f}/min"
        )

    @background_task
    async def _clean_up_delivered_events(self) -> None:
        """Remove acknowledged events from the backlog."""
        while not self.stop_event.is_set():
            async with self._event_backlog_lock:
                acknowledged = [
                    eid for eid, e in self._event_backlog.items() if e.state is State.ACKNOWLEDGED
                ]

                for eid in acknowledged:
                    del self._event_backlog[eid]

            await asyncio.sleep(10)

    async def _show_metric(self) -> None:
        """Continuously display backlog state distribution."""
        while not self.stop_event.is_set():
            async with self._event_backlog_lock:
                counter = Counter(event.state for event in self._event_backlog.values())
                total = len(self._event_backlog)

            print(
                f"\nEvents: {total},\n"
                f"Receiving: {counter[State.RECEIVING]:_},\n"
                f"Received: {counter[State.RECEIVED]:_},\n"
                f"Processing: {counter[State.PROCESSING]:_},\n"
                f"Processed: {counter[State.PROCESSED]:_},\n"
                f"Storing_output_1: {counter[State.STORING_OUTPUT_1]:_},\n"
                f"Stored_output_1: {counter[State.STORED_OUTPUT_1]:_},\n"
                f"Storing_output_2: {counter[State.STORING_OUTPUT_2]:_},\n"
                f"Stored_output_2: {counter[State.STORED_OUTPUT_2]:_},\n"
                f"Delivering: {counter[State.DELIVERING]:_},\n"
                f"Delivered: {counter[State.DELIVERED]:_},\n"
                f"Acknowledging: {counter[State.ACKNOWLEDGING]:_},\n"
                f"Acknowledged: {counter[State.ACKNOWLEDGED]:_}\n"
            )

            await asyncio.sleep(random.randint(1, 5) / 2)
