"""
Manipulator Module that takes a batch of input events, processes them and returns the updated
versions.
"""

import datetime
import logging
from datetime import datetime
from functools import reduce
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from logprep.generator.http.input import EventClassConfig


class Manipulator:
    """
    Manipulates batches of events by adding a tag and replacing the timestamp with the current date
    and time.
    """

    def __init__(self, config: "EventClassConfig", replace_timestamp: bool, tag: str):
        self.config = config
        self.replace_timestamp = replace_timestamp
        self.tag = tag
        self.log = logging.getLogger("Manipulator")
        self.timestamps_conf = self.config.timestamps
        if self.replace_timestamp and self.timestamps_conf is not None:
            self.manipulations = lambda event: self._replace_timestamps(self._add_tag(event))
        else:
            self.manipulations = self._add_tag

    def manipulate(self, events: List[dict]) -> List[dict]:
        """Manipulate Events, adds tags and replaces timestamps"""
        return list(map(self.manipulations, events))

    def _add_tag(self, event: dict) -> dict:
        if "tags" not in event.keys():
            event["tags"] = [self.tag]
        elif isinstance(event.get("tags"), list):
            event["tags"].append(self.tag)
        else:
            raise ValueError(
                f"Can't set tags {self.tag} to event {event},"
                f"because the field 'tags' exists already and is not of type list"
            )
        return event

    def _replace_timestamps(self, event: dict) -> dict:
        """Replace of all timestamps for one event."""
        number_timestamps = len(self.timestamps_conf)
        _ = list(map(self._replace_timestamp, [event] * number_timestamps, self.timestamps_conf))
        return event

    def _replace_timestamp(self, event: dict, timestamp) -> None:
        """Replace timestamp of the event."""
        field_key = timestamp.key
        timestamp_format = timestamp.format
        time_delta = timestamp.time_delta
        output_field_key = [event, *field_key.split(".")]
        target_key = output_field_key.pop()
        target_field = reduce(self._add_and_overwrite_key, output_field_key)
        target_field |= {target_key: (datetime.now() + time_delta).strftime(timestamp_format)}

    def _add_and_overwrite_key(self, sub_dict: dict, key: str) -> dict:
        """
        Overwrites a value in a dict for a given key.
        """
        current_value = sub_dict.get(key)
        if isinstance(current_value, dict):
            return current_value
        sub_dict.update({key: {}})
        return sub_dict.get(key)
