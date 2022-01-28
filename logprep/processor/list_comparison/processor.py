"""
This module contains functionality for checking if values exist or not exist in file lists. This processor implements
black- and whitelisting capabilities.
"""
from logging import Logger, DEBUG
from multiprocessing import current_process
from os import walk
from os.path import isdir, realpath, join
from time import time
from typing import List

from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class ListComparisonError(BaseException):
    """Base class for ListComparison related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'ListComparison ({name}): {message}')


class DuplicationError(ListComparisonError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = 'The following fields could not be written, because ' \
                  'one or more subfields existed and could not be extended: '
        message += ' '.join(skipped_fields)

        super().__init__(name, message)


class ListComparison(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        """
        Initializes the list_comparison processor.

        Parameters
        ----------
        name : str
            Name of the list_comparison processor (as referred to in the pipeline).
        tree_config : str
            Path to the configuration file which can prioritize fields and add conditional rules.
        logger : Logger
            Standard logger.
        """
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

    # pylint: disable=arguments-differ
    def add_rules_from_directory(self, rule_paths: List[str]):
        """
        Collect rules from given directory.

        Parameters
        ----------
        rules_paths : List[str]
            Path to the directory containing list_comparison rules.

        """
        for path in rule_paths:
            if not isdir(realpath(path)):
                raise NotARulesDirectoryError(self._name, path)

            for root, _, files in walk(path):
                json_files = []
                for file in files:
                    if (file.endswith('.json') or file.endswith('.yml')) and not file.endswith('_test.json'):
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
        """
        Collect rule(s) from a given file.

        Parameters
        ----------
        path : str
            Path to the file containing a list_comparison rule.

        """        
        try:
            return ListComparisonRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path, str(error)) from error

    def describe(self) -> str:
        """Return name of given processor instance."""
        return f'ListComparison ({self._name})'

    @TimeMeasurement.measure_time('list_comparison')
    def process(self, event: dict):
        """
        Process log message.

        Parameters
        ----------
        event : dict
            Current event log message to be processed.

        """         
        self._events_processed += 1
        self.ps.update_processed_count(self._events_processed)

        self._event = event

        for rule in self._tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float('{:.10f}'.format(time() - begin))
            idx = self._tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

    def _apply_rules(self, event, rule):
        """
        Apply matching rule to given log event. 
        In the process of doing so, add the result of comparing 
        the log with a given list to the specified subfield. This subfield will contain
        a list of list comparison results that might be based on multiple rules.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule : 
            Currently applied list comparison rule.

        """ 

        comparison_result, comparison_key = self._list_comparison(rule, event)

        if comparison_result is not None:
            output_field = rule.list_comparison_output_field+"."+comparison_key
            field_possible = add_field_to(event, output_field, comparison_result, True)
            if not field_possible:
                raise DuplicationError(self._name, [output_field])

    def _list_comparison(self, rule: ListComparisonRule, event: dict):
        """
        Check if field value violates block or allow list.
        Returns the result of the comparison (res_key), as well as a dictionary containing the result (key)
        and a list of filenames pertaining to said result (value).

        """

        field_value = self._get_dotted_field_value(event, rule.check_field)

        list_matches = [item[0] for item in rule.compare_set if item[1] == field_value]
        unmatched_files = {item[0] for item in rule.compare_set if item[1] != field_value}

        if len(list_matches) > 0:
            res_key = "in_list"
            result = [filename for filename in list_matches]
            return result, res_key

        elif len(list_matches) == 0:
            res_key = "not_in_list"
            result = [filename for filename in unmatched_files]
            return result, res_key
