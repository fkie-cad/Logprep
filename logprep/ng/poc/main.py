import asyncio

from async_pipeline.types import SizeLimitedQueue
from async_pipeline.worker.pipeline_worker import PipelineWorker
from mocked.mocking_functions import iter_input_pull
from mocked.mocking_types import Event
from pipeline_manager import ConcretePipelineManager

MAX_QUEUE_SIZE = 100_000

BATCH_SIZE = 20_000
BATCH_INTERVAL_S = 5


def get_workers() -> list[PipelineWorker[Event]]:
    input_worker: PipelineWorker[Event] = PipelineWorker(
        name="input_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=aiter(iter_input_pull()),
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler_name="handler_input_data",
    )

    processor_worker: PipelineWorker[Event] = PipelineWorker(
        name="processor_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=input_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler_name="handler_processor_data",
    )

    output_1_worker: PipelineWorker[Event] = PipelineWorker(
        name="output_1_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=processor_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler_name="handler_output_1_data",
    )

    output_2_worker: PipelineWorker[Event] = PipelineWorker(
        name="output_2_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=output_1_worker.out_queue,
        out_queue=SizeLimitedQueue(maxsize=MAX_QUEUE_SIZE),
        handler_name="handler_output_2_data",
    )

    acknowledge_worker: PipelineWorker[Event] = PipelineWorker(
        name="acknowledge_worker",
        batch_size=BATCH_SIZE,
        batch_interval_s=BATCH_INTERVAL_S,
        in_queue=output_2_worker.out_queue,
        out_queue=None,
        handler_name="handler_acknowledgement_data",
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

        pipeline_manager = ConcretePipelineManager(
            workers=get_workers(),
            loop=loop,
        )

        loop.run_until_complete(pipeline_manager.run())
    finally:
        loop.close()


async def async_main() -> None:
    pipeline_manager = ConcretePipelineManager(
        workers=get_workers(),
    )

    await pipeline_manager.run()


if __name__ == "__main__":
    # asyncio.run(async_main())
    main()
