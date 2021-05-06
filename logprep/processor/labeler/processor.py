"""This modules contains functionality for labeling log events."""

from typing import List
from logging import Logger

from os.path import realpath, isdir
from time import time
from multiprocessing import current_process

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.base.exceptions import *
from logprep.processor.labeler.exceptions import *
from logprep.processor.labeler.rule import LabelingRule

from logprep.processor.labeler.labeling_schema import LabelingSchema

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class Labeler(RuleBasedProcessor):
    """Processor used to label log events."""

    def __init__(self, name: str, logger: Logger):
        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name

        self._rules = []
        self._schema = None
        self._processed_count = 0

    def describe(self) -> str:
        return f'Labeler ({self._name})'

    def set_labeling_scheme(self, schema: LabelingSchema):
        """Set a labeling scheme."""
        if not isinstance(schema, LabelingSchema):
            raise InvalidLabelingSchemaError(self._name, 'Not a labeling schema: ' + str(schema))

        self._schema = schema

    def add_rules_from_directory(self, rules_dirs: List[str], include_parent_labels=False):
        if not isinstance(self._schema, LabelingSchema):
            raise NoLabelingSchemeDefinedError(self._name)

        for rules_dir in rules_dirs:
            if not isdir(realpath(rules_dir)):
                raise NotARulesDirectoryError(self._name, rules_dir)

            rule_paths = self._list_json_files_in_directory(rules_dir)
            for rule_path in rule_paths:
                rules = self._load_rule_from_file(rule_path)
                for rule in rules:
                    if include_parent_labels:
                        rule.add_parent_labels_from_schema(self._schema)
                    self._rules.append(rule)
        self._logger.debug('{} loaded {} rules ({})'.format(self.describe(), len(self._rules), current_process().name))
        self.ps.setup_rules(self._rules)

    def _load_rule_from_file(self, path: str) -> List[LabelingRule]:
        try:
            rules = LabelingRule.create_rules_from_file(path)
            for rule in rules:
                try:
                    rule.conforms_to_schema(self._schema)
                except RuleError as error:
                    raise RuleDoesNotConformToLabelingSchemaError(self._name, path) from error
            return rules
        except InvalidRuleDefinitionError:
            raise InvalidRuleFileError(self._name, path)

    def setup(self):
        if not isinstance(self._schema, LabelingSchema):
            raise NoLabelingSchemeDefinedError(self._name)

        if not self._rules:
            raise MustLoadRulesFirstError(self._name)

    @TimeMeasurement.measure_time('labeler')
    def process(self, event: dict):
        if not self._rules:
            raise MustLoadRulesFirstError(self._name)

        self._processed_count += 1
        self.ps.update_processed_count(self._processed_count)

        self._add_labels(event)
        self._convert_label_categories_to_sorted_list(event)

    def _add_labels(self, event: dict):
        for idx, rule in enumerate(self._rules):
            begin = time()
            if rule.matches(event):
                self._logger.debug('{} processing matching event'.format(self.describe()))
                rule.add_labels(event)

                processing_time = float('{:.10f}'.format(time() - begin))
                self.ps.update_per_rule(idx, processing_time, rule)

    @staticmethod
    def _convert_label_categories_to_sorted_list(event: dict):
        if 'label' in event:
            for category in event['label']:
                event['label'][category] = sorted(list(event['label'][category]))

    def events_processed_count(self) -> int:
        return self._processed_count
