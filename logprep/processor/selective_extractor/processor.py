"""
This module contains functionality to extract selectively fields from an incoming event.
The events will be returned and written to a specified kafka topic.
As the processor is applied to all events it does not need further filtering by rules.
"""

from logging import Logger
from typing import List
from logprep.abc.processor import Processor

from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class SelectiveExtractor(Processor):
    """Processor used to selectively extract fields from log events."""

    __slots__ = ["_filtered_events"]

    _filtered_events: List[tuple]

    rule_class = SelectiveExtractorRule

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._filtered_events = []

    def process(self, event: dict) -> tuple:
        super().process(event)
        if self._filtered_events:
            return self._filtered_events
        return None

    def _apply_rules(self, event, rule):
        """
        Generates a filtered event based on the incoming event and the configured
        extraction_fields list in processor configuration or from rule.
        The filtered fields and the target_topic are written to `self._filtered_events` list.

        Parameters
        ----------
        event: dict
            The incoming event that is currently being processed by logprep.

        rule: SelectiveExtractorRule
            The rule to apply

        """
        # filtered events has to be a tuple of (events, target)
        filtered_event = {}

        for field in rule.extracted_field_list:
            field_value = get_dotted_field_value(event, field)
            if field_value is not None:
                add_field_to(filtered_event, field, field_value)

        if filtered_event:
            self._filtered_events.append(([filtered_event], rule.target_topic))
