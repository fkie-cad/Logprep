"""This module contains functionality for resolving log event values using regex lists."""
import re
from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List

from time import time
from ruamel.yaml import YAML

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement

yaml = YAML(typ="safe", pure=True)


class GenericResolverError(BaseException):
    """Base class for GenericResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericResolver ({name}): {message}")


class DuplicationError(GenericResolverError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the Normalizer: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GenericResolver(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(
        self,
        name: str,
        specific_rules_dirs: list,
        generic_rules_dirs: list,
        tree_config: str,
        logger: Logger,
    ):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)

        self._event = None

        self._replacements_from_file = {}

        self.add_rules_from_directory(specific_rules_dirs, generic_rules_dirs)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """Add rules from given directory."""
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = GenericResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = GenericResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"({current_process().name})"
            )

        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter
            + [None] * self._specific_tree.rule_counter
        )
    # pylint: enable=arguments-differ

    def describe(self) -> str:
        """Describe the current processor"""
        return f"GenericResolver ({self._name})"

    @TimeMeasurement.measure_time("generic_resolver")
    def process(self, event: dict):
        """Process the current event"""
        self._event = event

        for rule in self._generic_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float(f"{time() - begin:.10f}")
            idx = self._generic_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._specific_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float(f"{time() - begin:.10f}")
            idx = self._specific_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        self.ps.increment_processed_count()

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        conflicting_fields = []

        if rule.resolve_from_file:
            if rule.resolve_from_file["path"] not in self._replacements_from_file:
                try:
                    with open(rule.resolve_from_file["path"], "r") as add_file:
                        add_dict = yaml.load(add_file)
                        if isinstance(add_dict, dict) and all(
                            isinstance(value, str) for value in add_dict.values()
                        ):
                            self._replacements_from_file[
                                rule.resolve_from_file["path"]
                            ] = add_dict
                        else:
                            raise GenericResolverError(
                                self._name,
                                f"Additions file "
                                f'\'{rule.resolve_from_file["path"]}\''
                                f" must be a dictionary with string values!",
                            )
                except FileNotFoundError as error:
                    raise GenericResolverError(
                        self._name,
                        f'Additions file \'{rule.resolve_from_file["path"]}'
                        f"' not found!",
                    ) from error

        for resolve_source, resolve_target in rule.field_mapping.items():
            keys = resolve_target.split(".")
            src_val = self._get_dotted_field_value(event, resolve_source)

            if rule.resolve_from_file and src_val:
                pattern = f'^{rule.resolve_from_file["pattern"]}$'
                replacements = self._replacements_from_file[
                    rule.resolve_from_file["path"]
                ]
                matches = re.match(pattern, src_val)
                if matches:
                    try:
                        dest_val = replacements.get(matches.group("mapping"))
                    except IndexError as error:
                        raise GenericResolverError(
                            self._name,
                            "Mapping group is missing in mapping file pattern!",
                        ) from error
                    if dest_val:
                        dict_ = event
                        for idx, key in enumerate(keys):
                            if key not in dict_:
                                if idx == len(keys) - 1:
                                    if rule.append_to_list:
                                        dict_[key] = dict_.get("key", [])
                                        if dest_val not in dict_[key]:
                                            dict_[key].append(dest_val)
                                    else:
                                        dict_[key] = dest_val
                                    break
                                dict_[key] = dict()
                            if isinstance(dict_[key], dict):
                                dict_ = dict_[key]
                            else:
                                if rule.append_to_list and isinstance(dict_[key], list):
                                    if dest_val not in dict_[key]:
                                        dict_[key].append(dest_val)
                                else:
                                    conflicting_fields.append(keys[idx])

            for pattern, dest_val in rule.resolve_list.items():
                if src_val and re.search(pattern, src_val):
                    dict_ = event
                    for idx, key in enumerate(keys):
                        if key not in dict_:
                            if idx == len(keys) - 1:
                                if rule.append_to_list:
                                    dict_[key] = dict_.get("key", [])
                                    dict_[key].append(dest_val)
                                else:
                                    dict_[key] = dest_val
                                break
                            dict_[key] = dict()
                        if isinstance(dict_[key], dict):
                            dict_ = dict_[key]
                        else:
                            conflicting_fields.append(keys[idx])
                    break

        if conflicting_fields:
            raise DuplicationError(self._name, conflicting_fields)
