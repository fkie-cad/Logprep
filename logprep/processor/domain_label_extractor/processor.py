""" This module contains functionality to split a domain into it's parts/labels. """
from logging import Logger, DEBUG
from multiprocessing import current_process
from os import walk
from os.path import isdir, realpath, join
from time import time
from typing import List

from tldextract import tldextract

from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement
from logprep.util.helper import add_field_to


class DomainLabelExtractorError(BaseException):
    """Base class for DomainLabelExtractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'DomainLabelExtractor ({name}): {message}')


class DuplicationError(DomainLabelExtractorError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = 'The following fields already existed and ' \
                  'were not overwritten by the DomainLabelExtractor: '
        message += ' '.join(skipped_fields)

        super().__init__(name, message)


class UnrecognizedTldError(DomainLabelExtractorError):
    """Raise if the domain tld is not recognized."""

    def __init__(self, name: str, domain: str):
        message = f"The given domain '{domain}' is malformed or has an unknown tld"
        super().__init__(name, message)


class DomainLabelExtractor(RuleBasedProcessor):
    """Splits a domain into it's parts/labels."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        """
        Initializes the DomainLabelExtractor processor.

        Parameters
        ----------
        name : str
            Name of the DomainLabelExtractor processor (as referred to in the pipeline).
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
            Path to the directory containing DomainLabelExtractor rules.

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
            Path to the file containing a DomainLabelExtractor rule.

        """

        try:
            return DomainLabelExtractorRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path, str(error)) from error

    def describe(self) -> str:
        """Return name of given processor instance."""
        return f'DomainLabelExtractor ({self._name})'

    @TimeMeasurement.measure_time('domain_label_extractor')
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

        self.event = event

        for rule in self._tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float('{:.10f}'.format(time() - begin))
            idx = self._tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

    def _apply_rules(self, event, rule: DomainLabelExtractorRule):
        """
        Apply matching rule to given log event. Such that a given domain, configured via rule, is split into it's
        labels and parts. The resulting subfields will be saved in the configured output field.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule : 
            Currently applied domain label extractor rule.
        """

        if self._field_exists(event, rule.target_field):
            domain = self._get_dotted_field_value(event, rule.target_field)
            labels = tldextract.extract(domain)

            if labels.suffix == '':
                # if no tld was recognized raise an error
                raise UnrecognizedTldError(self._name, domain)

            labels_dict = {
                'registered_domain': labels.domain + "." + labels.suffix,
                'top_level_domain': labels.suffix,
                'subdomain': labels.subdomain
            }

            # add results to event
            for label in labels_dict.keys():
                output_field = f"{rule.output_field}.{label}"
                adding_was_successful = add_field_to(event, output_field, labels_dict[label])

                if not adding_was_successful:
                    raise DuplicationError(self._name, [output_field])

    def events_processed_count(self):
        return self._events_processed
