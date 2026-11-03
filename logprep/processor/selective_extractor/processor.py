"""
|PROCESSOR_NAME|
================

The ``selective_extractor`` creates extra events from matching source events and sends
them to the outputs configured in each rule. Rules can select source fields directly,
load field names from a file, or build an event with ``event_template``. The source
event is preserved; missing template lookups add a warning tag and produce no extra event.

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

from logprep.processor.base.rule import Rule
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.field_mapping_template import (
    FieldMappingTemplateLookupError,
)
from logprep.util.field_mapping_template_helpers import (
    SOURCE_EVENT_CONTEXT,
    LazyContext,
    cleanup_missing_selection_parents,
)


class SelectiveExtractor(FieldManager):
    """Emit selected or templated event data to each matching rule's outputs."""

    rule_class = SelectiveExtractorRule

    def _apply_rules(self, event: dict, rule: Rule):
        """Evaluate a matching rule and append nonempty data with its output mappings.

        Runtime context provides the source event and lazy timestamp/UUID values.
        Missing template lookups preserve and tag the source event, record a warning,
        and skip the extra event. Legacy field selection honors ``ignore_missing_fields``.
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
                    SOURCE_EVENT_CONTEXT: event,
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
            self.result.data.append((filtered_event, rule.outputs))
