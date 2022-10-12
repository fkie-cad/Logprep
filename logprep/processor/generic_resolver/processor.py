"""
GenericResolver
---------------

The `generic_resolver` resolves log event values using regex lists.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - genericresolvername:
        type: generic_resolver
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
import re
from logging import Logger
from typing import List

from ruamel.yaml import YAML

from logprep.abc import Processor
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.helper import get_dotted_field_value

yaml = YAML(typ="safe", pure=True)


class GenericResolverError(BaseException):
    """Base class for GenericResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericResolver ({name}): {message}")


class DuplicationError(GenericResolverError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and were not overwritten by the Normalizer: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GenericResolver(Processor):
    """Resolve values in documents by referencing a mapping list."""

    __slots__ = ["_replacements_from_file"]

    _replacements_from_file: dict

    rule_class = GenericResolverRule

    def __init__(
        self,
        name: str,
        configuration: Processor.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._replacements_from_file = {}

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        conflicting_fields = []

        self.ensure_rules_from_file(rule)

        for resolve_source, resolve_target in rule.field_mapping.items():
            keys = resolve_target.split(".")
            src_val = get_dotted_field_value(event, resolve_source)

            if rule.resolve_from_file and src_val:
                pattern = f'^{rule.resolve_from_file["pattern"]}$'
                replacements = self._replacements_from_file[rule.resolve_from_file["path"]]
                matches = re.match(pattern, src_val)
                if matches:
                    mapping = matches.group("mapping") if "mapping" in matches.groupdict() else None
                    if mapping is None:
                        raise GenericResolverError(
                            self.name,
                            "Mapping group is missing in mapping file pattern!",
                        )
                    dest_val = replacements.get(mapping)
                    if dest_val:
                        for idx, key in enumerate(keys):
                            if key not in event:
                                if idx == len(keys) - 1:
                                    if rule.append_to_list:
                                        event[key] = event.get("key", [])
                                        if dest_val not in event[key]:
                                            event[key].append(dest_val)
                                    else:
                                        event[key] = dest_val
                                    break
                                event[key] = {}
                            if isinstance(event[key], dict):
                                event = event[key]
                            else:
                                if rule.append_to_list and isinstance(event[key], list):
                                    if dest_val not in event[key]:
                                        event[key].append(dest_val)
                                else:
                                    conflicting_fields.append(keys[idx])

            for pattern, dest_val in rule.resolve_list.items():
                if src_val and re.search(pattern, src_val):
                    for idx, key in enumerate(keys):
                        if key not in event:
                            if idx == len(keys) - 1:
                                if rule.append_to_list:
                                    event[key] = event.get("key", [])
                                    event[key].append(dest_val)
                                else:
                                    event[key] = dest_val
                                break
                            event[key] = {}
                        if isinstance(event[key], dict):
                            event = event[key]
                        else:
                            conflicting_fields.append(keys[idx])
                    break

        if conflicting_fields:
            raise DuplicationError(self.name, conflicting_fields)

    def ensure_rules_from_file(self, rule):
        """loads rules from file"""
        if rule.resolve_from_file:
            if rule.resolve_from_file["path"] not in self._replacements_from_file:
                try:
                    with open(rule.resolve_from_file["path"], "r", encoding="utf8") as add_file:
                        add_dict = yaml.load(add_file)
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
