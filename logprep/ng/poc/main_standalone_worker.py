import asyncio

from async_pipeline.types import SizeLimitedQueue
from async_pipeline.worker.worker import Worker
from mocked.mocking_functions import iter_input_pull
from mocked.mocking_types import Event

MAX_QUEUE_SIZE = 100_000

BATCH_SIZE = 2_500
BATCH_INTERVAL_S = 5


# ---- handlers (match: (list[Event]) -> list[Event]) ----

acked = 0


async def handler_input_data(events: list[Event]) -> list[Event]:
    print(f"[handler_input_data] batch={len(events)}")
    await asyncio.sleep(1)
    return events


async def handler_processor_data(events: list[Event]) -> list[Event]:
    print(f"[handler_processor_data] batch={len(events)}")
    await asyncio.sleep(1)
    return events


async def handler_output_1_data(events: list[Event]) -> list[Event]:
    print(f"[handler_output_1_data] batch={len(events)}")
    await asyncio.sleep(1)
    return events


async def handler_output_2_data(events: list[Event]) -> list[Event]:
    print(f"[handler_output_2_data] batch={len(events)}")
    await asyncio.sleep(1)
    return events


async def handler_acknowledgement_data(events: list[Event]) -> list[Event]:
    global acked

    print(f"[handler_acknowledgement_data] batch={len(events)}")
    await asyncio.sleep(1)

    acked += len(events)
    print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> Total {acked=}")
    return events


def get_workers() -> list[Worker[Event]]:
    input_worker: Worker[Event] = Worker(
        name="input_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=aiter(iter_input_pull()),
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler=handler_input_data,
    )

    processor_worker: Worker[Event] = Worker(
        name="processor_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=input_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler=handler_processor_data,
    )

    output_1_worker: Worker[Event] = Worker(
        name="output_1_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=processor_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler=handler_output_1_data,
    )

    output_2_worker: Worker[Event] = Worker(
        name="output_2_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=output_1_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler=handler_output_2_data,
    )

    acknowledge_worker: Worker[Event] = Worker(
        name="acknowledge_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=output_2_worker.out_queue,
        out_queue=None,
        handler=handler_acknowledgement_data,
    )

    return [
        input_worker,
        processor_worker,
        output_1_worker,
        output_2_worker,
        acknowledge_worker,
    ]


def main() -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        workers = get_workers()
        tasks = [loop.create_task(w.run()) for w in workers]

        # Demo: keep running; Ctrl+C stops
        loop.run_until_complete(asyncio.gather(*tasks))
    finally:
        loop.close()


async def async_main() -> None:
    workers = get_workers()
    await asyncio.gather(*(asyncio.create_task(w.run()) for w in workers))


if __name__ == "__main__":
    # asyncio.run(async_main())
    main()
