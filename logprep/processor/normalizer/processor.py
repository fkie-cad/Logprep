"""This module contains a Normalizer that copies specific values to standardized fields."""
import html
import os
from typing import Optional, Tuple, List, Union
from filelock import FileLock
import json
from logging import Logger, DEBUG
from pathlib import Path

from ruamel.yaml import YAML
from time import time
from functools import reduce
from multiprocessing import current_process
import re

from datetime import datetime
from dateutil import parser
from pytz import timezone
import arrow
import calendar

import ujson

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning
from logprep.processor.normalizer.exceptions import DuplicationError, NormalizerError
from logprep.processor.normalizer.rule import NormalizerRule

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement

yaml = YAML(typ="safe", pure=True)


class Normalizer(RuleBasedProcessor):
    """Normalize log events by copying specific values to standardized fields."""

    def __init__(
        self,
        name: str,
        specific_rules_dirs: list,
        generic_rules_dirs: list,
        tree_config: Optional[str],
        logger: Logger,
        regex_mapping: str = None,
        html_replace_fields: str = None,
        grok_patterns: str = None,
        count_grok_pattern_matches: dict = None,
    ):
        super().__init__(name, tree_config, logger)
        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name
        self._event = None
        self._conflicting_fields = []

        self._regex_mapping = regex_mapping
        self._html_replace_fields = html_replace_fields

        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)

        self._count_grok_pattern_matches = count_grok_pattern_matches
        if count_grok_pattern_matches:
            self._grok_matches_path = count_grok_pattern_matches["count_directory_path"]
            self._file_lock_path = count_grok_pattern_matches.get(
                "lock_file_path", "count_grok_pattern_matches.lock"
            )
            self._grok_cnt_period = count_grok_pattern_matches["write_period"]
            self._grok_cnt_timer = time()
            self._grok_pattern_matches = {}

        NormalizerRule.additional_grok_patterns = grok_patterns

        with open(regex_mapping, "r") as file:
            self._regex_mapping = yaml.load(file)

        if html_replace_fields:
            with open(html_replace_fields, "r") as file:
                self._html_replace_fields = yaml.load(file)

        self.add_rules_from_directory(specific_rules_dirs, generic_rules_dirs)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = NormalizerRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = NormalizerRule.create_rules_from_file(rule_path)
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

    def describe(self) -> str:
        return f"Normalizer ({self._name})"

    @TimeMeasurement.measure_time("normalizer")
    def process(self, event: dict):
        self._event = event
        self._conflicting_fields.clear()
        self._apply_rules()
        if self._count_grok_pattern_matches:
            self._write_grok_matches()

        self.ps.increment_processed_count()
        try:
            self._raise_warning_if_fields_already_existed()
        except DuplicationError as error:
            raise ProcessingWarning(str(error)) from error

    def _write_grok_matches(self):
        """Write count of matches for each grok pattern into a file if configured time has passed.

        If enabled, grok pattern matches are being counted.
        This method writes them into a file after a configured time has passed.
        First, it reads the existing counts from the file, then it sums them with the current
        counts and writes the result back into the file.

        One file is created per day if anything is written.
        """
        now = time()
        if now < self._grok_cnt_timer + self._grok_cnt_period:
            return
        self._grok_cnt_timer = now

        current_date = arrow.now().date()
        weekday = calendar.day_name[current_date.weekday()].lower()

        file_name = f"{current_date}_{weekday}.json"
        file_path = os.path.join(self._grok_matches_path, file_name)
        Path(self._grok_matches_path).mkdir(parents=True, exist_ok=True)
        with FileLock(self._file_lock_path):
            json_dict = {}
            if os.path.isfile(file_path):
                with open(file_path, "r") as grok_json_file:
                    json_dict = json.load(grok_json_file)

            for key, value in self._grok_pattern_matches.items():
                json_dict[key] = json_dict.get(key, 0) + value
                self._grok_pattern_matches[key] = 0

            with open(file_path, "w") as grok_json_file:
                json_dict = dict(reversed(sorted(json_dict.items(), key=lambda items: items[1])))
                json.dump(json_dict, grok_json_file, indent=4)

    def _try_add_field(self, target: Union[str, List[str]], value: str):
        target, value = self._get_transformed_value(target, value)

        if self._field_exists(self._event, target):
            if self._get_dotted_field_value(self._event, target) != value:
                self._conflicting_fields.append(target)
        else:
            self._add_field(target, value)

    def _get_transformed_value(self, target: Union[str, List[str]], value: str) -> Tuple[str, str]:
        if isinstance(target, list):
            matching_pattern = self._regex_mapping.get(target[1], None)
            if matching_pattern:
                substitution_pattern = target[2]
                value = re.sub(matching_pattern, substitution_pattern, value)
            target = target[0]
        return target, value

    def _add_field(self, dotted_field: str, value: Union[str, int]):
        fields = dotted_field.split(".")
        missing_fields = ujson.loads(ujson.dumps(fields))
        dict_ = self._event
        for field in fields:
            if isinstance(dict_, dict) and field in dict_:
                dict_ = dict_[field]
                missing_fields.pop(0)
            else:
                break
        if not isinstance(dict_, dict):
            self._conflicting_fields.append(dotted_field)
            return
        for field in missing_fields[:-1]:
            dict_[field] = {}
            dict_ = dict_[field]
        dict_[missing_fields[-1]] = value

        if self._html_replace_fields and dotted_field in self._html_replace_fields:
            if self._has_html_entity(value):
                dict_[missing_fields[-1] + "_decodiert"] = html.unescape(value)

    @staticmethod
    def _has_html_entity(value):
        return re.search("&#[0-9]{2,4};", value)

    def _replace_field(self, dotted_field: str, value: str):
        fields = dotted_field.split(".")
        reduce(lambda dict_, key: dict_[key], fields[:-1], self._event)[fields[-1]] = value

    def _apply_rules(self):
        """Normalizes Windows Event Logs.

        The rules in this function are applied on a first-come, first-serve basis: If a rule copies
        a source field to a normalized field and a subsequent rule tries to write the same
        normalized field, it will not be overwritten and a ProcessingWarning will be raised
        as a last step after processing the current event has finished. The same holds true if a
        rule tries to overwrite a field that already exists in the original event. The rules should
        be written in a way that no such warnings are produced during normal operation because each
        warning should be an indicator of incorrect rules or unexpected/changed events.
        """
        for rule in self._generic_tree.get_matching_rules(self._event):
            begin = time()
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug(f"{self.describe()} processing generic matching event")
            self._try_add_grok(rule)
            self._try_add_timestamps(rule)
            for before, after in rule.substitutions.items():
                self._try_normalize_event_data_field(before, after)

            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._generic_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

        for rule in self._specific_tree.get_matching_rules(self._event):
            begin = time()
            if self._logger.isEnabledFor(DEBUG):
                self._logger.debug(f"{self.describe()} processing specific matching event")
            self._try_add_grok(rule)
            self._try_add_timestamps(rule)
            for before, after in rule.substitutions.items():
                self._try_normalize_event_data_field(before, after)

            processing_time = float("{:.10f}".format(time() - begin))
            idx = self._specific_tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

    def _try_add_grok(self, rule: NormalizerRule):
        for source_field, grok in rule.grok.items():
            source_value = self._get_dotted_field_value(self._event, source_field)
            if source_value is None:
                continue

            if self._count_grok_pattern_matches:
                matches = grok.match(source_value, self._grok_pattern_matches)
            else:
                matches = grok.match(source_value)
            for normalized_field, field_value in matches.items():
                if field_value is not None:
                    self._try_add_field(normalized_field, field_value)

    def _try_add_timestamps(self, rule: NormalizerRule):
        for source_field, normalization in rule.timestamps.items():
            timestamp_normalization = normalization["timestamp"]

            source_timestamp = self._get_dotted_field_value(self._event, source_field)

            if source_timestamp is None:
                continue

            allow_override = timestamp_normalization.get("allow_override", True)
            normalization_target = timestamp_normalization["destination"]
            source_formats = timestamp_normalization["source_formats"]
            source_timezone = timestamp_normalization["source_timezone"]
            destination_timezone = timestamp_normalization["destination_timezone"]

            timestamp = None
            format_parsed = False
            for source_format in source_formats:
                try:
                    if source_format == "ISO8601":
                        timestamp = parser.isoparse(source_timestamp)

                    elif source_format == "UNIX":
                        # convert UNIX Epoch timestamp string to int (with or without milliseconds)
                        new_stamp = int(source_timestamp)
                        if len(source_timestamp) > 10:
                            # Epoch with milliseconds
                            timestamp = datetime.fromtimestamp(
                                new_stamp / 1000, timezone(source_timezone)
                            )
                        else:
                            # Epoch without milliseconds
                            timestamp = datetime.fromtimestamp(new_stamp, timezone(source_timezone))
                    else:
                        timestamp = datetime.strptime(source_timestamp, source_format)
                        # Set year to current year if no year was provided in timestamp
                        if timestamp.year == 1900:
                            timestamp = timestamp.replace(year=datetime.now().year)
                    format_parsed = True
                    break
                except ValueError:
                    pass
            if not format_parsed:
                raise NormalizerError(
                    self._name,
                    'Could not parse source timestamp "{}" with formats "{}"'.format(
                        source_timestamp, source_formats
                    ),
                )

            time_zone = timezone(source_timezone)
            if not timestamp.tzinfo:
                timestamp = time_zone.localize(timestamp)
                timestamp = timezone(source_timezone).normalize(timestamp)
            timestamp = timestamp.astimezone(timezone(destination_timezone))
            timestamp = timezone(destination_timezone).normalize(timestamp)

            converted_time = timestamp.isoformat()
            converted_time = converted_time.replace("+00:00", "Z")

            if allow_override:
                self._replace_field(normalization_target, converted_time)
            else:
                self._try_add_field(normalization_target, converted_time)

    def _try_normalize_event_data_field(self, field: str, normalized_field: str):
        if self._field_exists(self._event, field):
            self._try_add_field(normalized_field, self._get_dotted_field_value(self._event, field))

    def _raise_warning_if_fields_already_existed(self):
        if self._conflicting_fields:
            raise DuplicationError(self._name, self._conflicting_fields)

    def shut_down(self):
        """Stop processing of this processor and finish outstanding actions.

        Optional: Called when stopping the pipeline

        """
        if self._count_grok_pattern_matches:
            self._write_grok_matches()
