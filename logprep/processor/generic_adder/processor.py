"""This modules contains functionality for adding fields using regex lists."""

from typing import List
from logging import Logger, DEBUG

from os import walk
from os.path import isdir, realpath, join

from multiprocessing import current_process

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class GenericAdderError(BaseException):
    """Base class for GenericAdder related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'GenericAdder ({name}): {message}')


class DuplicationError(GenericAdderError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = 'The following fields already existed and ' \
                  'were not overwritten by the GenericAdder: '
        message += ' '.join(skipped_fields)

        super().__init__(name, message)


class GenericAdder(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

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
            return GenericAdderRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path, str(error)) from error

    def describe(self) -> str:
        return f'GenericAdder ({self._name})'

    @TimeMeasurement.measure_time('generic_adder')
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

        for dotted_field, value in rule.add.items():
            keys = dotted_field.split('.')
            dict_ = event
            for idx, key in enumerate(keys):
                if key not in dict_:
                    if idx == len(keys) - 1:
                        dict_[key] = value
                        break
                    dict_[key] = dict()

                if isinstance(dict_[key], dict):
                    dict_ = dict_[key]
                else:
                    conflicting_fields.append(keys[idx])

        if conflicting_fields:
            raise DuplicationError(self._name, conflicting_fields)
