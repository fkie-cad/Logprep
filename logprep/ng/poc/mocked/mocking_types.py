import enum
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


class State(str, enum.Enum):
    RECEIVING = "receiving"
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    STORING_OUTPUT_1 = "storing_output_1"
    STORED_OUTPUT_1 = "stored_output_1"
    STORING_OUTPUT_2 = "storing_output_2"
    STORED_OUTPUT_2 = "stored_output_2"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    ACKNOWLEDGING = "acknowledging"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class Event:
    payload: str
    state: State = State.RECEIVING
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    errors: list[str] = field(default_factory=list)

    def update_payload(self, payload: dict[str, Any]) -> None:
        """Convenience helper for the demo: replace payload JSON."""

        self.payload = json.dumps(payload)

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Iterate over the JSON payload as key/value pairs.

        This makes `Event` usable in contexts that expect an iterable without
        relying on the previously incorrect `__iter__` signature.
        """

        try:
            data = json.loads(self.payload)
        except json.JSONDecodeError:
            return iter(())

        if isinstance(data, dict):
            return iter(data.items())
        return iter(())
