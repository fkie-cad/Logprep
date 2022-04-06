"""This module contains functionality to split timestamps into fields containing their parts."""

from typing import List
from logging import Logger, DEBUG

from multiprocessing import current_process
from os import walk
from os.path import isdir, realpath, join
from time import time

from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzlocal
from logprep.framework.rule_tree.rule_tree import RuleTree

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.datetime_extractor.rule import DateTimeExtractorRule
from logprep.processor.base.exceptions import (
    NotARulesDirectoryError,
    InvalidRuleDefinitionError,
    InvalidRuleFileError,
)

from logprep.util.processor_stats import ProcessorStats, StatsClassesController
from logprep.util.time_measurement import TimeMeasurement


class DateTimeExtractorError(BaseException):
    """Base class for DateTimeExtractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"DateTimeExtractor ({name}): {message}")


class DateTimeExtractor(RuleBasedProcessor):
    """Split timestamps into fields containing their parts."""

    def __init__(self, name: str, configuration: dict, logger: Logger):
        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config=tree_config, logger=logger)
        self.ps = ProcessorStats()
        self._local_timezone = tzlocal()
        self._local_timezone_name = self._get_timezone_name(self._local_timezone)
        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs,
            specific_rules_dirs=specific_rules_dirs,
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = DateTimeExtractorRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = DateTimeExtractorRule.create_rules_from_file(rule_path)
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
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

    def _load_rules_from_file(self, path: str):
        try:
            return DateTimeExtractorRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path) from error

    def describe(self) -> str:
        return f"DateTimeExtractor ({self._name})"

    @TimeMeasurement.measure_time("datetime_extractor")
    def process(self, event: dict):
        self._event = event

        for rule in self._specific_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(self._event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._specific_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._generic_tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(self._event, rule)
            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._generic_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        self.ps.increment_processed_count()

    @staticmethod
    def _get_timezone_name(local_timezone):
        tz_name = datetime.now(local_timezone).strftime("%z")
        local_timezone_name = "UTC"
        if tz_name != "+0000":
            local_timezone_name += f"{tz_name[:-2]}:{tz_name[-2:]}"
        return local_timezone_name

    def _apply_rules(self, event, rule):
        datetime_field = rule.datetime_field
        destination_field = rule.destination_field

        if destination_field and self._field_exists(event, datetime_field):
            datetime_value = self._get_dotted_field_value(event, datetime_field)

            parsed_timestamp = parse(datetime_value).astimezone(self._local_timezone)

            split_timestamp = {
                "year": parsed_timestamp.year,
                "month": parsed_timestamp.month,
                "day": parsed_timestamp.day,
                "hour": parsed_timestamp.hour,
                "minute": parsed_timestamp.minute,
                "second": parsed_timestamp.second,
                "microsecond": parsed_timestamp.microsecond,
                "weekday": parsed_timestamp.strftime("%A"),
                "timezone": self._local_timezone_name,
            }

            if split_timestamp:
                if destination_field not in event.keys():
                    event[destination_field] = split_timestamp
