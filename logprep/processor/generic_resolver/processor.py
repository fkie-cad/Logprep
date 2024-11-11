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
from typing import Union

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class GenericResolver(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = GenericResolverRule

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        conflicting_fields = []

        source_values = []
        for source_field, target_field in rule.field_mapping.items():
            source_value = get_dotted_field_value(event, source_field)
            source_values.append(source_value)
            if source_value is None:
                continue

            # FILE
            if rule.resolve_from_file:
                pattern = f'^{rule.resolve_from_file["pattern"]}$'
                replacements = rule.resolve_from_file["additions"]
                matches = re.match(pattern, source_value)
                if matches:
                    dest_val = replacements.get(matches.group("mapping"))
                    if dest_val:
                        success = self._add_uniquely_to_list(event, rule, target_field, dest_val)
                        if not success:
                            conflicting_fields.append(target_field)

            # LIST
            for pattern, dest_val in rule.resolve_list.items():
                if re.search(pattern, source_value):
                    success = add_field_to(
                        event,
                        target_field,
                        dest_val,
                        extends_lists=rule.extend_target_list,
                        overwrite_output_field=rule.overwrite_target,
                    )
                    if not success:
                        conflicting_fields.append(target_field)
                    break
        self._handle_missing_fields(event, rule, rule.field_mapping.keys(), source_values)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

    @staticmethod
    def _add_uniquely_to_list(
        event: dict,
        rule: GenericResolverRule,
        target: str,
        content: Union[str, float, int, list, dict],
    ) -> bool:
        """Extend list if content is not already in the list"""
        add_success = True
        target_val = get_dotted_field_value(event, target)
        target_is_list = isinstance(target_val, list)
        if rule.extend_target_list and not target_is_list:
            empty_list = []
            add_success &= add_field_to(
                event,
                target,
                empty_list,
                overwrite_output_field=rule.overwrite_target,
            )
            if add_success:
                target_is_list = True
                target_val = empty_list
        if target_is_list and content in target_val:
            return add_success
        add_success = add_field_to(event, target, content, extends_lists=rule.extend_target_list)
        return add_success
