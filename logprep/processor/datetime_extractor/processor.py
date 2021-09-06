"""This modules contains functionality to split timestamps into fields containing their parts."""

from typing import List
from logging import Logger, DEBUG

from multiprocessing import current_process
from os import walk
from os.path import isdir, realpath, join

from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzlocal

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.datetime_extractor.rule import DateTimeExtractorRule
from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class DateTimeExtractorError(BaseException):
    """Base class for DateTimeExtractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'DateTimeExtractor ({name}): {message}')


class DateTimeExtractor(RuleBasedProcessor):
    """Split timestamps into fields containing their parts."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._local_timezone = tzlocal()
        self._local_timezone_name = self._get_timezone_name(self._local_timezone)

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
            self._logger.debug(f'{self.describe()} loaded {self._tree.rule_counter} '
                               f'rules ({current_process().name})')

        self.ps.setup_rules([None] * self._tree.rule_counter)
    # pylint: enable=arguments-differ

    def _load_rules_from_file(self, path: str):
        try:
            return DateTimeExtractorRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path) from error

    def describe(self) -> str:
        return f'DateTimeExtractor ({self._name})'

    @TimeMeasurement.measure_time('datetime_extractor')
    def process(self, event: dict):
        self._events_processed += 1
        self.ps.update_processed_count(self._events_processed)

        self._event = event

        matching_rules = self._tree.get_matching_rules(event)

        if matching_rules:
            for rule in matching_rules:
                self._apply_rules(event, rule)

    @staticmethod
    def _get_timezone_name(local_timezone):
        tz_name = datetime.now(local_timezone).strftime('%z')
        local_timezone_name = 'UTC'
        if tz_name != '+0000':
            local_timezone_name += f'{tz_name[:-2]}:{tz_name[-2:]}'
        return local_timezone_name

    def _apply_rules(self, event, rule):
        datetime_field = rule.datetime_field
        destination_field = rule.destination_field

        if destination_field and self._field_exists(event, datetime_field):
            datetime_value = self._get_dotted_field_value(event, datetime_field)

            parsed_timestamp = parse(datetime_value).astimezone(self._local_timezone)

            split_timestamp = {
                'year': parsed_timestamp.year,
                'month': parsed_timestamp.month,
                'day': parsed_timestamp.day,
                'hour': parsed_timestamp.hour,
                'minute': parsed_timestamp.minute,
                'second': parsed_timestamp.second,
                'microsecond': parsed_timestamp.microsecond,
                'weekday': parsed_timestamp.strftime('%A'),
                'timezone': self._local_timezone_name
            }

            if split_timestamp:
                if destination_field not in event.keys():
                    event[destination_field] = split_timestamp
