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
from logging import Logger
from typing import Union

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import get_dotted_field_value, add_field_to


class GenericResolverError(BaseException):
    """Base class for GenericResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericResolver ({name}): {message}")


class GenericResolver(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    __slots__ = ["_replacements_from_file"]

    _replacements_from_file: dict

    rule_class = GenericResolverRule

    def __init__(
        self,
        name: str,
        configuration: FieldManager.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._replacements_from_file = {}

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        conflicting_fields = []
        self.ensure_rules_from_file(rule)

        source_values = []
        for source_field, target_field in rule.field_mapping.items():
            source_value = get_dotted_field_value(event, source_field)
            source_values.append(source_value)
            if source_value is None:
                continue

            # FILE
            if rule.resolve_from_file:
                pattern = f'^{rule.resolve_from_file["pattern"]}$'
                replacements = self._replacements_from_file[rule.resolve_from_file["path"]]
                matches = re.match(pattern, source_value)
                if matches:
                    mapping = matches.group("mapping") if "mapping" in matches.groupdict() else None
                    if mapping is None:
                        raise GenericResolverError(
                            self.name,
                            "Mapping group is missing in mapping file pattern!",
                        )
                    dest_val = replacements.get(mapping)
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

    def ensure_rules_from_file(self, rule):
        """loads rules from file"""
        if rule.resolve_from_file:
            if rule.resolve_from_file["path"] not in self._replacements_from_file:
                try:
                    add_dict = GetterFactory.from_string(rule.resolve_from_file["path"]).get_yaml()
                    if isinstance(add_dict, dict) and all(
                        isinstance(value, str) for value in add_dict.values()
                    ):
                        self._replacements_from_file[rule.resolve_from_file["path"]] = add_dict
                    else:
                        raise GenericResolverError(
                            self.name,
                            f"Additions file "
                            f'\'{rule.resolve_from_file["path"]}\''
                            f" must be a dictionary with string values!",
                        )
                except FileNotFoundError as error:
                    raise GenericResolverError(
                        self.name,
                        f'Additions file \'{rule.resolve_from_file["path"]}' f"' not found!",
                    ) from error
