"""This modules contains functionality for resolving log event values using regex lists."""

from typing import List
from logging import Logger, DEBUG

from os import walk
from os.path import isdir, realpath, join

from multiprocessing import current_process

import re

from ruamel.yaml import YAML

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement

yaml = YAML(typ='safe', pure=True)


class GenericResolverError(BaseException):
    """Base class for GenericResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'GenericResolver ({name}): {message}')


class DuplicationError(GenericResolverError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = 'The following fields already existed and ' \
                  'were not overwritten by the Normalizer: '
        message += ' '.join(skipped_fields)

        super().__init__(name, message)


class GenericResolver(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._replacements_from_file = {}

    # pylint: disable=arguments-differ
    def add_rules_from_directory(self, rule_paths: List[str]):
        """Add rules from given directory."""
        for path in rule_paths:
            if not isdir(realpath(path)):
                raise NotARulesDirectoryError(self._name, path)

            for root, _, files in walk(path):
                json_files = []
                for file in files:
                    if (file.endswith('.json') or file.endswith('.yml')) and not file.endswith(
                            '_test.json'):
                        json_files.append(file)
                for file in json_files:
                    rules = self._load_rules_from_file(join(root, file))
                    for rule in rules:
                        self._tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f'{self.describe()} loaded {self._tree.rule_counter} rules '
                               f'({current_process().name})')

        self.ps.setup_rules([None] * self._tree.rule_counter)
    # pylint: enable=arguments-differ

    def _load_rules_from_file(self, path: str):
        try:
            return GenericResolverRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path) from error

    def describe(self) -> str:
        return f'GenericResolver ({self._name})'

    @TimeMeasurement.measure_time('generic_resolver')
    def process(self, event: dict):
        self._events_processed += 1
        self.ps.update_processed_count(self._events_processed)

        self._event = event

        matching_rules = self._tree.get_matching_rules(event)

        if matching_rules:
            for rule in matching_rules:
                self._apply_rules(event, rule)

    def _apply_rules(self, event, rule):
        conflicting_fields = list()

        if rule.resolve_from_file:
            if rule.resolve_from_file['path'] not in self._replacements_from_file:
                try:
                    with open(rule.resolve_from_file['path'], 'r') as add_file:
                        add_dict = yaml.load(add_file)
                        if isinstance(add_dict, dict) and all(
                                isinstance(value, str) for value in add_dict.values()):
                            self._replacements_from_file[rule.resolve_from_file['path']] = add_dict
                        else:
                            raise GenericResolverError(self._name,
                                                       f'Additions file '
                                                       f'\'{rule.resolve_from_file["path"]}\''
                                                       f' must be a dictionary with string values!')
                except FileNotFoundError as error:
                    raise GenericResolverError(self._name,
                                               f'Additions file \'{rule.resolve_from_file["path"]}'
                                               f'\' not found!') from error

        for resolve_source, resolve_target in rule.field_mapping.items():
            keys = resolve_target.split('.')
            src_val = self._get_dotted_field_value(event, resolve_source)

            if rule.resolve_from_file and src_val:
                pattern = f'^{rule.resolve_from_file["pattern"]}$'
                replacements = self._replacements_from_file[rule.resolve_from_file['path']]
                matches = re.match(pattern, src_val)
                if matches:
                    try:
                        dest_val = replacements.get(matches.group('mapping'))
                    except IndexError as error:
                        raise GenericResolverError(self._name,
                                                   'Mapping group is missing in mapping file '
                                                   'pattern!') from error
                    if dest_val:
                        dict_ = event
                        for idx, key in enumerate(keys):
                            if key not in dict_:
                                if idx == len(keys) - 1:
                                    if rule.append_to_list:
                                        dict_[key] = dict_.get('key', [])
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
                                    dict_[key] = dict_.get('key', [])
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
