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
from logprep.util.field_mapping_template import (
    FieldMappingTemplateLookupError,
    LazyContext,
)
from logprep.util.helper import FieldValue, get_dotted_field_list


def cleanup_missing_selection_parents(
    filtered_event: dict[str, FieldValue],
    source_fields: list[str],
) -> None:
    """Remove empty generated parents from a legacy field selection in place.

    Use after evaluating a template built by ``source_fields_to_fmt`` with
    missing fields skipped. ``source_fields`` contains the same dotted paths
    used to build that template. Explicitly selected values are preserved,
    including empty dictionaries and their contents; only their generated
    parent dictionaries are traversed and removed when empty.
    """
    selected_paths = {tuple(get_dotted_field_list(field)) for field in source_fields}

    def remove_empty_parents(mapping, parent_path=()):
        for name, value in list(mapping.items()):
            path = (*parent_path, name)

            if path in selected_paths:
                continue

            if isinstance(value, dict):
                remove_empty_parents(value, path)
                if not value:
                    del mapping[name]

    remove_empty_parents(filtered_event)


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
                    "source_event": event,
                    "context": LazyContext(
                        {
                            "now": lambda: datetime.now(timezone.utc).isoformat(),
                            "id": lambda: str(uuid4()),
                        }
                    ),
                },
            )
        except FieldMappingTemplateLookupError as error:
            if config.ignore_missing_fields:
                self._handle_warning_error(
                    event, rule, error, failure_tags=["_selective_extractor_missing_field_warning"]
                )
                return
            raise ProcessingCriticalError(str(error), rule) from error

        if extracted_event:
            self.result.data.append((extracted_event, rule.outputs))
