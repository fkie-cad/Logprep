"""
GenericResolver
===============

The `generic_resolver` resolves log event values using regex lists.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - genericresolvername:
        type: generic_resolver
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.generic_resolver.processor.GenericResolver.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.generic_resolver.rule
"""

import re

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class GenericResolver(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = GenericResolverRule

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        source_field_values = [
            get_dotted_field_value(event, source_field)
            for source_field in rule.field_mapping.keys()
        ]
        self._handle_missing_fields(event, rule, rule.field_mapping.keys(), source_field_values)
        conflicting_fields = []
        for source_field, target_field in rule.field_mapping.items():
            source_field_value = get_dotted_field_value(event, source_field)
            if source_field_value is None:
                continue
            content = self._find_content_of_first_matching_pattern(rule, source_field_value)
            if not content:
                continue
            current_content = get_dotted_field_value(event, target_field)
            if isinstance(current_content, list) and content in current_content:
                continue
            if rule.extend_target_list and current_content is None:
                content = [content]
            try:
                add_field_to(
                    event,
                    fields={target_field: content},
                    rule=rule,
                    extends_lists=rule.extend_target_list,
                    overwrite_target_field=rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

    def _find_content_of_first_matching_pattern(self, rule, source_field_value):
        if rule.resolve_from_file:
            pattern = f'^{rule.resolve_from_file["pattern"]}$'
            replacements = rule.resolve_from_file["additions"]
            matches = re.match(pattern, source_field_value)
            if matches:
                content = replacements.get(matches.group("mapping"))
                if content:
                    return content
        for pattern, content in rule.resolve_list.items():
            if re.search(pattern, source_field_value):
                return content
