import json
import random
import time
import uuid
from collections.abc import AsyncIterator

from logprep.ng.poc.mocked.mocking_types import Event


# HELPER
async def iter_input_pull() -> AsyncIterator[Event]:
    while True:
        event_id = uuid.uuid4()
        yield Event(
            event_id=event_id,
            payload=json.dumps({"additional_data": f"{event_id}"}),
        )


async def store(events: list[Event], topic: str) -> None:
    # blocking sleep
    time.sleep(random.randint(1, 5) / 10)


async def commit(events: list[Event]) -> None:
    # blocking sleep
    time.sleep(random.randint(1, 5) / 10)
