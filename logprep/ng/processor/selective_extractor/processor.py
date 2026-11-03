"""
|PROCESSOR_NAME|
================

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
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.selective_extractor.processor.SelectiveExtractor.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.selective_extractor.rule
"""

import typing
from datetime import datetime, timezone
from uuid import uuid4

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.ng.processor.selective_extractor.filtered_event import FilteredEvent
from logprep.ng.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.processor.base.rule import Rule
from logprep.processor.selective_extractor.processor import (
    cleanup_missing_selection_parents,
)
from logprep.util.field_mapping_template import (
    FieldMappingTemplateLookupError,
    LazyContext,
)
from logprep.util.helper import FieldValue


class SelectiveExtractor(FieldManager):
    """Processor used to selectively extract fields from log events."""

    rule_class = SelectiveExtractorRule

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
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
        rule = typing.cast(SelectiveExtractorRule, rule)
        config = rule.config

        # Preserve legacy missing-field behavior for source_fields and extract_from_file.
        compat_skip_missing = bool(config.source_fields) and config.ignore_missing_fields

        if config.source_fields and not config.ignore_missing_fields:
            field_values = self._get_field_values(event, config.source_fields)
            if self._handle_missing_fields(event, rule, config.source_fields, field_values):
                return

        try:
            filtered_event = rule.compiled_template.evaluate(
                runtime_context={
                    "source_event": event,
                    "context": LazyContext(
                        {
                            "now": lambda: datetime.now(timezone.utc).isoformat(),
                            "id": lambda: str(uuid4()),
                        }
                    ),
                },
                skip_missing_fields=compat_skip_missing,
            )
        except FieldMappingTemplateLookupError as error:
            self._handle_warning_error(
                event, rule, error, failure_tags=["_selective_extractor_missing_field_warning"]
            )
            return

        if compat_skip_missing:
            cleanup_missing_selection_parents(filtered_event, config.source_fields)

        if filtered_event:
            for spec in rule.outputs:
                self._event.extra_data.append(
                    FilteredEvent(
                        filtered_event,
                        output_name=spec.output_name,
                        output_target=spec.output_target,
                    )
                )
