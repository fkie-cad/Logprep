import json
import random
import time

from mocked.mocking_types import Event


class Processor:
    @staticmethod
    def process(events: list[Event]) -> list[Event]:
        for event in events:
            new_payload = json.loads(event.payload)
            new_payload["processed"] = True
            event.payload = json.dumps(new_payload)

        # blocking sleep
        time.sleep(random.randint(1, 5) / 10)

        return events
