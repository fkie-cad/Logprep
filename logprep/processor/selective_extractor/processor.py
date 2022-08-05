"""
SelectiveExtractor
------------------

The `selective_extractor` is a processor that allows to write field values of a given log message to
a different Kafka topic. The output topic is configured via the pipeline yml, while the fields to
be extracted are specified by means of a list which is also specified in the pipeline configuration
as a file path. This processor is applied to all messages, because of that it does not need further
rules to specify it's behavior.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - selectiveextractorname:
        type: selective_extractor
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
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
        configuration: Processor.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._filtered_events = []

    def process(self, event: dict) -> tuple:
        self._filtered_events = []
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
