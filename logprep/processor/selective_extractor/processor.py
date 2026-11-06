"""
|PROCESSOR_NAME|
================

The ``selective_extractor`` creates extra events from matching source events and sends
them to the outputs configured in each rule.
Rules can select source fields directly, load field names from a file, or build an event with ``event_template``.
The source event is preserved on success.
Missing lookups produce no extra event: they cause a warning by default, or a critical error when ``ignore_missing_fields`` is false.

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

from logprep.processor.base.exceptions import ProcessingCriticalError
from logprep.processor.base.rule import Rule
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.field_template import (
    FieldTemplateLookupError,
)
from logprep.util.field_template_helpers import (
    SOURCE_EVENT_CONTEXT,
    LazyContext,
)


class SelectiveExtractor(FieldManager):
    """Emit selected or templated event data to each matching rule's outputs."""

    rule_class = SelectiveExtractorRule

    def _apply_rules(self, event: dict, rule: Rule):
        """Evaluate a matching rule and append non-empty data with its output mappings.

        Runtime context provides the source event and lazy timestamp/UUID values.
        Missing lookups skip the extra event, recording a warning when
        ``ignore_missing_fields`` is true, or raising a critical error otherwise.
        """
        rule = typing.cast(SelectiveExtractorRule, rule)
        config = rule.config

        try:
            extracted_event = rule.compiled_template.evaluate(
                runtime_context={
                    SOURCE_EVENT_CONTEXT: event,
                    "context": LazyContext(
                        {
                            "now": lambda: datetime.now(timezone.utc).isoformat(),
                            "id": lambda: str(uuid4()),
                        }
                    ),
                },
            )
        except FieldTemplateLookupError as error:
            if config.ignore_missing_fields:
                self._handle_warning_error(
                    event, rule, error, failure_tags=["_selective_extractor_missing_field_warning"]
                )
                return
            raise ProcessingCriticalError(str(error), rule) from error

        if extracted_event:
            self.result.data.append((extracted_event, rule.outputs))
