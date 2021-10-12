"""This module contains a Dropper that deletes specified fields."""

from typing import List, Optional, Union
from logging import Logger, DEBUG

from time import time
from multiprocessing import current_process

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.dropper.rule import DropperRule

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class DropperError(BaseException):
    """Base class for Dropper related exceptions."""

    def __init__(self, name, message):
        super().__init__(f'Dropper ({name}): {message}')


class Dropper(RuleBasedProcessor):
    """Normalize log events by copying specific values to standardized fields."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, tree_config, logger)
        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name
        self._events_processed = 0
        self._event = None
        self._tree = RuleTree(config_path=tree_config)

    def add_rules_from_directory(self, rules_dirs: List[str]):
        for rules_dir in rules_dirs:
            rule_paths = self._list_json_files_in_directory(rules_dir)
            for rule_path in rule_paths:
                rules = DropperRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug('{} loaded {} rules ({})'.format(self.describe(), self._tree.rule_counter,
                                                                current_process().name))
        self.ps.setup_rules([None] * self._tree.rule_counter)

    def describe(self) -> str:
        return f'Dropper ({self._name})'

    @TimeMeasurement.measure_time('dropper')
    def process(self, event: dict):
        self._events_processed += 1
        self.ps.update_processed_count(self._events_processed)

        self._event = event
        self._apply_rules()

    def _field_exists(self, dotted_field: str) -> bool:
        fields = dotted_field.split('.')
        dict_ = self._event
        for field in fields:
            if field in dict_:
                dict_ = dict_[field]
            else:
                return False
        return True

    def _get_dotted_field_value(self, dotted_field: str) -> Optional[Union[dict, list, str]]:
        fields = dotted_field.split('.')
        dict_ = self._event
        for field in fields:
            if field in dict_:
                dict_ = dict_[field]
        return dict_

    def _traverse_dict(self, dict_: dict, sub_fields, drop_full: bool):
        sub_field = sub_fields[0] if sub_fields else None
        if isinstance(dict_, dict) and sub_field in dict_ and (isinstance(dict_[sub_field], dict) and dict_[sub_field]):
            self._traverse_dict(dict_[sub_field], sub_fields[1:], drop_full)
            if dict_[sub_field] == {} and drop_full:
                del dict_[sub_field]
        elif sub_field in dict_.keys():
            del dict_[sub_field]

    def _drop_field(self, dotted_field: str, drop_full: bool):
        sub_fields = dotted_field.split('.')
        self._traverse_dict(self._event, sub_fields, drop_full)

    def _apply_rules(self):
        """Drops fields from event Logs."""

        for rule in self._tree.get_matching_rules(self._event):
            begin = time()

            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug('{} processing matching event'.format(self.describe()))
            for drop_field in rule.fields_to_drop:
                self._try_dropping_field(drop_field, rule.drop_full)

                processing_time = float('{:.10f}'.format(time() - begin))
                idx = self._tree.get_rule_id(rule)
                self.ps.update_per_rule(idx, processing_time)

    def _try_dropping_field(self, field: str, drop_full: bool):
        if self._field_exists(field):
            self._drop_field(field, drop_full)

    def events_processed_count(self) -> int:
        return self._events_processed
