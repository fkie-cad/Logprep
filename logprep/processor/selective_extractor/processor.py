"""
SelectiveExtractor
==================

The `selective_extractor` is a processor that allows to write field values of a given log message to
a different Kafka topic. The output topic is configured via the pipeline yml, while the fields to
be extracted are specified by means of a list which is also specified in the pipeline configuration
as a file path. This processor is applied to all messages, because of that it does not need further
rules to specify it's behavior.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - selectiveextractorname:
        type: selective_extractor
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.selective_extractor.processor.SelectiveExtractor.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.selective_extractor.rule
"""

from logging import Logger
from typing import List, Tuple

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.helper import add_field_to, get_source_fields_dict


class SelectiveExtractor(FieldManager):
    """Processor used to selectively extract fields from log events."""

    __slots__ = ("_extra_data",)

    _extra_data: List[Tuple[List, str, str]]
    """has to be a list of tuples with a List of event, target_output, target_topic"""

    rule_class = SelectiveExtractorRule

    def __init__(
        self,
        name: str,
        configuration: FieldManager.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._extra_data = []

    def process(self, event: dict) -> List[Tuple[List, str, str]]:
        self._extra_data = []
        super().process(event)
        if self._extra_data:
            return self._extra_data
        return None

    def _apply_rules(self, event: dict, rule: SelectiveExtractorRule):
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
        flattened_fields = get_source_fields_dict(event, rule)
        self._handle_missing_fields(event, rule, flattened_fields.keys(), flattened_fields.values())
        flattened_fields = {
            dotted_field: content
            for dotted_field, content in flattened_fields.items()
            if content is not None
        }
        if flattened_fields:
            filtered_event = {}
            for field, content in flattened_fields.items():
                add_field_to(filtered_event, field, content)
            self._extra_data.append(([filtered_event], rule.outputs))
