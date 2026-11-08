# pylint: disable=missing-docstring
# pylint: disable=protected-access

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence

import pytest

from logprep.ng.util.workflow.config import WorkerConfig
from logprep.ng.util.workflow.worker import (
    BatchingWorker,
    SequentialWorker,
    SizeLimitedQueue,
    Worker,
    WorkerOrchestrator,
    create_worker_graph,
    iterate_workers_topologically,
)

pytestmark = pytest.mark.timeout(10)

INTERVAL_S = 0.01
TIMEOUT_S = 1.0


class BlockingHandler:
    """Holds every batch until released and records how many run at once."""

    def __init__(self) -> None:
        self.batches: list[list[int]] = []
        self.running = 0
        self.max_running = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, batch: Sequence[int]) -> None:
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        self.started.set()
        try:
            await self.release.wait()
            self.batches.append(list(batch))
        finally:
            self.running -= 1


class Recorder:
    """Records every item it is called with."""

    def __init__(self) -> None:
        self.items: list[int] = []

    async def __call__(self, item: int) -> None:
        self.items.append(item)


@pytest.fixture(name="handler")
def fixture_handler() -> BlockingHandler:
    return BlockingHandler()


@pytest.fixture(name="queue")
def fixture_queue() -> SizeLimitedQueue[int]:
    return SizeLimitedQueue(maxsize=10)


@pytest.fixture(name="worker")
def fixture_worker(handler: BlockingHandler, queue: SizeLimitedQueue[int]) -> BatchingWorker[int]:
    return BatchingWorker(
        name="processing_worker",
        handler=handler,
        in_queue=queue,
        out_queues=[],
        config=WorkerConfig(queue_size=10, batch_size=2, batch_interval_s=INTERVAL_S),
    )


async def async_iter(*items: int) -> AsyncIterator[int]:
    for item in items:
        yield item


async def wait_until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(TIMEOUT_S):
        while not condition():
            await asyncio.sleep(0.001)


@pytest.mark.parametrize("maxsize", [0, -1])
def test_size_limited_queue_must_be_bounded(maxsize: int) -> None:
    with pytest.raises(ValueError, match="bounded"):
        SizeLimitedQueue(maxsize=maxsize)


async def test_sequential_worker_handles_items_from_a_queue_until_stopped() -> None:
    handler = Recorder()
    queue: SizeLimitedQueue[int] = SizeLimitedQueue(10)
    worker = SequentialWorker("processing_worker", handler, queue, [])

    run = asyncio.create_task(worker.run())
    for item in (1, 2):
        await queue.put(item)
    await wait_until(lambda: handler.items == [1, 2])
    assert not run.done()

    await worker.stop()
    await asyncio.wait_for(run, timeout=TIMEOUT_S)
    assert handler.items == [1, 2]


async def test_sequential_worker_stops_when_its_iterator_is_exhausted() -> None:
    handler = Recorder()
    worker = SequentialWorker("input_worker", handler, async_iter(1, 2), [])

    await asyncio.wait_for(worker.run(), timeout=TIMEOUT_S)

    assert handler.items == [1, 2]


def create_chain() -> list[SequentialWorker[int]]:
    """input -> processing -> output"""
    handler = Recorder()
    processing_queue: SizeLimitedQueue[int] = SizeLimitedQueue(10)
    output_queue: SizeLimitedQueue[int] = SizeLimitedQueue(10)
    return [
        SequentialWorker("input_worker", handler, async_iter(), [processing_queue]),
        SequentialWorker("processing_worker", handler, processing_queue, [output_queue]),
        SequentialWorker("output_worker", handler, output_queue, []),
    ]


def test_create_worker_graph_maps_workers_to_their_successors() -> None:
    source, processing, sink = create_chain()

    graph = create_worker_graph([sink, source, processing])

    assert graph == {source: [processing], processing: [sink], sink: []}


def test_iterate_workers_topologically_goes_from_source_to_sink() -> None:
    source, processing, sink = create_chain()

    groups = [list(group) for group in iterate_workers_topologically([sink, processing, source])]

    assert groups == [[source], [processing], [sink]]


async def test_orchestrator_passes_items_through_the_chain_and_stops_on_the_stop_event() -> None:
    collector = Recorder()
    output_queue: SizeLimitedQueue[int] = SizeLimitedQueue(10)

    async def forward(item: int | None) -> None:
        if item is not None:
            await output_queue.put(item)

    async def endless_input() -> AsyncIterator[int | None]:
        for item in (1, 2):
            yield item
        while True:  # like an input polling an empty source
            await asyncio.sleep(0.001)
            yield None

    workers: list[Worker] = [
        SequentialWorker("input_worker", forward, endless_input(), [output_queue]),
        SequentialWorker("output_worker", collector, output_queue, []),
    ]
    stop_event = asyncio.Event()
    run = asyncio.create_task(WorkerOrchestrator(workers).run(stop_event, TIMEOUT_S, TIMEOUT_S))
    await wait_until(lambda: collector.items == [1, 2])

    stop_event.set()
    await asyncio.wait_for(run, timeout=2 * TIMEOUT_S)
    assert collector.items == [1, 2]


async def test_flushes_when_the_batch_is_full(
    worker: BatchingWorker[int], handler: BlockingHandler
) -> None:
    handler.release.set()

    async with asyncio.timeout(TIMEOUT_S):
        await worker._handle_next(1)
        await worker._handle_next(2)

    assert handler.batches == [[1, 2]]


async def test_flushes_after_the_batch_interval(
    worker: BatchingWorker[int], handler: BlockingHandler
) -> None:
    handler.release.set()

    await worker._handle_next(1)

    await wait_until(lambda: handler.batches == [[1]])


async def test_run_flushes_the_buffer_on_stop(
    worker: BatchingWorker[int], handler: BlockingHandler, queue: SizeLimitedQueue[int]
) -> None:
    handler.release.set()
    run = asyncio.create_task(worker.run())

    await queue.put(1)
    await worker.stop()
    await asyncio.wait_for(run, timeout=TIMEOUT_S)

    assert handler.batches == [[1]]


async def test_size_flush_waits_for_a_running_timer_flush(
    worker: BatchingWorker[int], handler: BlockingHandler
) -> None:
    await worker._handle_next(1)
    await asyncio.wait_for(handler.started.wait(), timeout=TIMEOUT_S)  # timer flush of [1] runs

    await worker._handle_next(2)
    size_flush = asyncio.create_task(worker._handle_next(3))  # flushes [2, 3]
    await asyncio.sleep(INTERVAL_S * 5)
    handler.release.set()
    await asyncio.wait_for(size_flush, timeout=TIMEOUT_S)

    assert handler.max_running == 1
    assert handler.batches == [[1], [2, 3]]


async def test_run_returns_only_after_a_running_timer_flush(
    worker: BatchingWorker[int], handler: BlockingHandler, queue: SizeLimitedQueue[int]
) -> None:
    run = asyncio.create_task(worker.run())
    await queue.put(1)
    await asyncio.wait_for(handler.started.wait(), timeout=TIMEOUT_S)  # timer flush of [1] runs

    await worker.stop()
    await asyncio.sleep(INTERVAL_S * 5)
    assert not run.done()

    handler.release.set()
    await asyncio.wait_for(run, timeout=TIMEOUT_S)
    assert handler.batches == [[1]]
