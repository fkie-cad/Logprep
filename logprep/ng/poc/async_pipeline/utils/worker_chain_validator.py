"""
Worker chain validation utilities.

This module validates queue-based wiring between workers to ensure a strict,
linear pipeline topology. It provides deterministic ordering for execution and
fails fast on ambiguous or unsafe configurations.
"""

import asyncio
from typing import Any, TypeGuard, TypeVar

from async_pipeline.worker.worker import Worker

W = TypeVar("W", bound=Worker[Any])


def _is_async_queue(obj: object) -> TypeGuard[asyncio.Queue[Any]]:
    """Return True if *obj* is an asyncio.Queue."""
    return isinstance(obj, asyncio.Queue)


def _object_identity(obj: object) -> int:
    """Return identity key used for queue wiring validation."""
    return id(obj)


def _input_queue_identity(worker: Worker[Any]) -> int | None:
    """Return identity of the worker input queue, if queue-backed."""
    input_source = worker.in_queue
    return _object_identity(input_source) if _is_async_queue(input_source) else None


def _output_queue_identity(worker: Worker[Any]) -> int | None:
    """Return identity of the worker output queue, if configured."""
    output_queue = worker.out_queue
    return _object_identity(output_queue) if output_queue is not None else None


def validate_and_sort_linear_worker_chain(workers: list[W]) -> list[W]:
    """
    Validate and order workers as a strict linear chain.

    Ensures a single start worker, prohibits fan-in/fan-out, detects cycles,
    and verifies full chain connectivity based on queue identity wiring.
    """
    if not workers:
        return []

    consumer_by_input_queue_id: dict[int, W] = {}

    for worker in workers:
        queue_id = _input_queue_identity(worker)

        if queue_id is None:
            continue

        if queue_id in consumer_by_input_queue_id:
            raise ValueError(
                f"Invalid worker chain: multiple consumers detected for input queue id {queue_id}."
            )

        consumer_by_input_queue_id[queue_id] = worker

    producer_by_output_queue_id: dict[int, W] = {}

    for worker in workers:
        queue_id = _output_queue_identity(worker)

        if queue_id is None:
            continue

        if queue_id in producer_by_output_queue_id:
            raise ValueError(
                f"Invalid worker chain: multiple producers detected for output queue id {queue_id}."
            )

        producer_by_output_queue_id[queue_id] = worker

    produced_output_queue_ids = set(producer_by_output_queue_id.keys())

    start_workers: list[W] = []

    for worker in workers:
        input_queue_id = _input_queue_identity(worker)

        if input_queue_id is None:
            start_workers.append(worker)
        elif input_queue_id not in produced_output_queue_ids:
            start_workers.append(worker)

    start_workers = list({id(w): w for w in start_workers}.values())

    if len(start_workers) != 1:
        names = ", ".join(worker.name for worker in start_workers) or "none"

        raise ValueError(
            f"Invalid worker chain: expected exactly one start worker, "
            f"got {len(start_workers)} ({names})."
        )

    start_worker = start_workers[0]

    ordered_workers: list[W] = []
    visited_worker_ids: set[int] = set()

    current_worker: W = start_worker

    while True:
        worker_identity = id(current_worker)

        if worker_identity in visited_worker_ids:
            raise ValueError(
                f"Invalid worker chain: cycle detected at worker {current_worker.name}."
            )

        visited_worker_ids.add(worker_identity)
        ordered_workers.append(current_worker)

        if current_worker.out_queue is None:
            break

        next_queue_id = _object_identity(current_worker.out_queue)
        next_worker = consumer_by_input_queue_id.get(next_queue_id)

        if next_worker is None:
            break

        current_worker = next_worker

    if len(ordered_workers) != len(workers):
        unreachable_workers = [
            worker.name for worker in workers if id(worker) not in visited_worker_ids
        ]

        raise ValueError(
            "Invalid worker chain: chain is not fully connected. "
            f"Unreachable workers: {', '.join(unreachable_workers)}."
        )

    return ordered_workers
