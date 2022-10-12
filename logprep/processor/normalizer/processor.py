"""
Normalizer
----------
The Normalizer copies specific values to configurable fields.

Example
^^^^^^^

..  code-block:: yaml
    :linenos:

    - normalizername:
        type: normalizer
        generic_rules:
            - tests/testdata/labeler_rules/rules/
        specific_rules:
            - tests/testdata/labeler_rules/rules/
        hash_salt: a_secret_tasty_ingredient
        regex_mapping: tests/testdata/unit/normalizer/normalizer_regex_mapping.yml
        html_replace_fields: tests/testdata/unit/normalizer/html_replace_fields.yml
        count_grok_pattern_matches:
            count_directory_path: "path/to/directory"
            write_period: 0.1
            lock_file_path: "path/to/lock/file"

"""
import calendar
import html
import json
import os
import re
from datetime import datetime
from functools import reduce
from logging import Logger
from pathlib import Path
from time import time
from typing import List, Optional, Tuple, Union

import arrow
from attr import define, field, validators
from dateutil import parser
from filelock import FileLock
from pytz import timezone
from ruamel.yaml import YAML

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.normalizer.exceptions import DuplicationError, NormalizerError
from logprep.processor.normalizer.rule import NormalizerRule
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import file_validator, directory_validator

yaml = YAML(typ="safe", pure=True)


class Normalizer(Processor):
    """Normalize log events by copying specific values to standardized fields."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """config description for Normalizer"""

        regex_mapping: str = field(validator=file_validator)
        """Path to regex mapping file with regex keywords that are replaced with regex expressions
            by the normalizer."""
        html_replace_fields: Optional[str] = field(default=None, validator=file_validator)
        """Path to yaml file with html replace fields"""
        count_grok_pattern_matches: Optional[dict] = field(
            default=None, validator=validators.optional(validators.instance_of(dict))
        )
        """Optional configuration to count matches of grok patterns.
            Counting will be disabled if this value is omitted."""
        grok_patterns: Optional[str] = field(default=None, validator=directory_validator)
        """Optional path to a directory with grok patterns."""

    __slots__ = [
        "_conflicting_fields",
        "_regex_mapping",
        "_html_replace_fields",
        "_count_grok_pattern_matches",
        "_grok_matches_path",
        "_file_lock_path",
        "_grok_cnt_period",
        "_grok_cnt_timer",
        "_grok_pattern_matches",
    ]

    _grok_pattern_matches: dict

    _grok_cnt_timer: float

    _grok_cnt_period: str

    _file_lock_path: str

    _grok_matches_path: str

    _count_grok_pattern_matches: str

    _regex_mapping: str

    _html_replace_fields: str

    _conflicting_fields: list

    rule_class = NormalizerRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        self._event = None
        self._conflicting_fields = []

        self._regex_mapping = configuration.regex_mapping
        self._html_replace_fields = configuration.html_replace_fields

        self._count_grok_pattern_matches = configuration.count_grok_pattern_matches
        if self._count_grok_pattern_matches:
            self._grok_matches_path = self._count_grok_pattern_matches["count_directory_path"]
            self._file_lock_path = self._count_grok_pattern_matches.get(
                "lock_file_path", "count_grok_pattern_matches.lock"
            )
            self._grok_cnt_period = self._count_grok_pattern_matches["write_period"]
            self._grok_cnt_timer = time()
            self._grok_pattern_matches = {}

        NormalizerRule.additional_grok_patterns = configuration.grok_patterns

        with open(self._regex_mapping, "r", encoding="utf8") as file:
            self._regex_mapping = yaml.load(file)

        if self._html_replace_fields:
            with open(self._html_replace_fields, "r", encoding="utf8") as file:
                self._html_replace_fields = yaml.load(file)
        super().__init__(name=name, configuration=configuration, logger=logger)

    # pylint: enable=arguments-differ

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
                with open(file_path, "r", encoding="utf8") as grok_json_file:
                    json_dict = json.load(grok_json_file)

            for key, value in self._grok_pattern_matches.items():
                json_dict[key] = json_dict.get(key, 0) + value
                self._grok_pattern_matches[key] = 0

            with open(file_path, "w", encoding="utf8") as grok_json_file:
                json_dict = dict(reversed(sorted(json_dict.items(), key=lambda items: items[1])))
                json.dump(json_dict, grok_json_file, indent=4)

    def _try_add_field(self, event: dict, target: Union[str, List[str]], value: str):
        target, value = self._get_transformed_value(target, value)

        if self._field_exists(event, target):
            if get_dotted_field_value(event, target) != value:
                self._conflicting_fields.append(target)
        else:
            self._add_field(event, target, value)

    def _get_transformed_value(self, target: Union[str, List[str]], value: str) -> Tuple[str, str]:
        if isinstance(target, list):
            matching_pattern = self._regex_mapping.get(target[1], None)
            if matching_pattern:
                substitution_pattern = target[2]
                value = re.sub(matching_pattern, substitution_pattern, value)
            target = target[0]
        return target, value

    def _add_field(self, event: dict, dotted_field: str, value: Union[str, int]):
        fields = dotted_field.split(".")
        missing_fields = json.loads(json.dumps(fields))
        for field in fields:
            if isinstance(event, dict) and field in event:
                event = event[field]
                missing_fields.pop(0)
            else:
                break
        if not isinstance(event, dict):
            self._conflicting_fields.append(dotted_field)
            return
        for field in missing_fields[:-1]:
            event[field] = {}
            event = event[field]
        event[missing_fields[-1]] = value

        if self._html_replace_fields and dotted_field in self._html_replace_fields:
            if self._has_html_entity(value):
                event[missing_fields[-1] + "_decodiert"] = html.unescape(value)

    @staticmethod
    def _has_html_entity(value):
        return re.search("&#[0-9]{2,4};", value)

    @staticmethod
    def _replace_field(event: dict, dotted_field: str, value: str):
        fields = dotted_field.split(".")
        reduce(lambda dict_, key: dict_[key], fields[:-1], event)[fields[-1]] = value

    def process(self, event: dict):
        self._conflicting_fields.clear()
        super().process(event)
        if self._count_grok_pattern_matches:
            self._write_grok_matches()
        try:
            self._raise_warning_if_fields_already_existed()
        except DuplicationError as error:
            raise ProcessingWarning(str(error)) from error

    def _apply_rules(self, event, rule):
        """Normalizes Windows Event Logs.

        The rules in this function are applied on a first-come, first-serve basis: If a rule copies
        a source field to a normalized field and a subsequent rule tries to write the same
        normalized field, it will not be overwritten and a ProcessingWarning will be raised
        as a last step after processing the current event has finished. The same holds true if a
        rule tries to overwrite a field that already exists in the original event. The rules should
        be written in a way that no such warnings are produced during normal operation because each
        warning should be an indicator of incorrect rules or unexpected/changed events.
        """
        self._apply_grok(event, rule)
        self._apply_timestamp_normalization(event, rule)
        for source_field, target_field in rule.substitutions.items():
            self._apply_field_copy(event, source_field, target_field)

    def _apply_grok(self, event: dict, rule: NormalizerRule):
        """
        Applies the grok pattern of a given NormalizerRule to a given event, by matching the field
        value against the grok pattern. If no pattern matches a grok failure field is written to the
        event (if configured).
        """
        one_matched = False
        source_field, source_value = None, None
        for source_field, grok in rule.grok.items():
            source_value = get_dotted_field_value(event, source_field)
            if source_value is None:
                continue
            matches = self._get_grok_matches(grok, source_value)
            for normalized_field, field_value in matches.items():
                if field_value is not None:
                    self._try_add_field(event, normalized_field, field_value)
                    one_matched = True
        if not one_matched:
            self._write_grok_failure_field(event, rule, source_field, source_value)

    def _get_grok_matches(self, grok, source_value):
        if self._count_grok_pattern_matches:
            return grok.match(source_value, self._grok_pattern_matches)
        return grok.match(source_value)

    def _write_grok_failure_field(self, event, rule, source_field, source_value):
        """
        If grok patterns exist and are configured with a failure target field, then add the source
        field and the first 100 characters of the grok patterns' target field to the event.
        The source field path, which is usually converted to subfields according to the dotted field
        path, is converted first to a path that is split by '>'. That way the separate fields are
        not all added to the event and instead only a path identifier is added. For example the
        source_field 'field.subfield.key' will be converted to 'field>subfield>key'. This makes
        it easy to understand in which field the grok failure happened without having to add
        all subfields separately.

        Parameters
        ----------
        event : dict
            The event that is currently being processed
        rule : NormalizerRule
            The current rule that should be applied to the event
        source_field : str
            The dotted source field path to which the grok pattern was applied to
        source_value : str
            The content of the source_field
        """
        if not rule.grok.items():
            return
        grok_wrapper = rule.grok.get(source_field)
        failure_target_field = grok_wrapper.failure_target_field
        if grok_wrapper.failure_target_field:
            source_field_path = source_field.replace(".", ">")
            add_field_to(event, f"{failure_target_field}.{source_field_path}", source_value[:100])

    def _apply_timestamp_normalization(self, event: dict, rule: NormalizerRule):
        """
        Normalizes the timestamps of an event by applying the given rule.
        """
        for source_field, normalization in rule.timestamps.items():
            source_timestamp = get_dotted_field_value(event, source_field)
            if source_timestamp is None:
                continue

            timestamp_normalization = normalization.get("timestamp")
            timestamp = self._transform_timestamp(source_timestamp, timestamp_normalization)
            timestamp = self._convert_timezone(timestamp, timestamp_normalization)
            iso_timestamp = timestamp.isoformat().replace("+00:00", "Z")
            self._write_normalized_timestamp(event, iso_timestamp, timestamp_normalization)

    def _transform_timestamp(self, source_timestamp, timestamp_normalization):
        source_timezone = timestamp_normalization["source_timezone"]
        timestamp = None
        format_parsed = False
        source_formats = timestamp_normalization["source_formats"]
        for source_format in source_formats:
            try:
                if source_format == "ISO8601":
                    timestamp = parser.isoparse(source_timestamp)
                elif source_format == "UNIX":
                    new_stamp = int(source_timestamp)
                    if len(source_timestamp) > 10:
                        timestamp = datetime.fromtimestamp(
                            new_stamp / 1000, timezone(source_timezone)
                        )
                    else:
                        timestamp = datetime.fromtimestamp(new_stamp, timezone(source_timezone))
                else:
                    timestamp = datetime.strptime(source_timestamp, source_format)
                    if timestamp.year == 1900:
                        timestamp = timestamp.replace(year=datetime.now().year)
                format_parsed = True
                break
            except ValueError:
                pass
        if not format_parsed:
            error_message = (
                f"Could not parse source timestamp "
                f"{source_timestamp}' with formats '{source_formats}'"
            )
            raise NormalizerError(self.name, error_message)
        return timestamp

    def _convert_timezone(self, timestamp, timestamp_normalization):
        source_timezone = timestamp_normalization["source_timezone"]
        destination_timezone = timestamp_normalization["destination_timezone"]
        time_zone = timezone(source_timezone)
        if not timestamp.tzinfo:
            timestamp = time_zone.localize(timestamp)
            timestamp = timezone(source_timezone).normalize(timestamp)
        timestamp = timestamp.astimezone(timezone(destination_timezone))
        timestamp = timezone(destination_timezone).normalize(timestamp)
        return timestamp

    def _write_normalized_timestamp(self, event, iso_timestamp, timestamp_normalization):
        allow_override = timestamp_normalization.get("allow_override", True)
        normalization_target = timestamp_normalization["destination"]
        if allow_override:
            self._replace_field(event, normalization_target, iso_timestamp)
        else:
            self._try_add_field(event, normalization_target, iso_timestamp)

    def _apply_field_copy(self, event: dict, source_field: str, target_field: str):
        if self._field_exists(event, source_field):
            source_value = get_dotted_field_value(event, source_field)
            self._try_add_field(event, target_field, source_value)

    def _raise_warning_if_fields_already_existed(self):
        if self._conflicting_fields:
            raise DuplicationError(self.name, self._conflicting_fields)

    def shut_down(self):
        """
        Stop processing of this processor and finish outstanding actions.
        Optional: Called when stopping the pipeline
        """
        if self._count_grok_pattern_matches:
            self._write_grok_matches()
