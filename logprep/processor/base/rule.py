"""This module is the superclass for all rule classes."""

import json
from abc import abstractmethod
from os.path import basename, splitext
from typing import Set, Optional

from attr import define
from ruamel.yaml import YAML

from logprep.metrics.metric import Metric, calculate_new_average
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.json_handling import is_json

yaml = YAML(typ="safe", pure=True)


class Rule:
    """Check if documents match a filter and add labels them."""

    @define(kw_only=True)
    class RuleMetrics(Metric):
        """Tracks statistics about the current rule"""

        _number_of_matches: int = 0
        """Tracks how often this rule matched regarding an event."""
        _mean_processing_time: float = 0.0
        _mean_processing_time_sample_counter: int = 0

        def update_mean_processing_time(self, new_sample):
            """Updates the mean processing time of this rule"""
            new_avg, new_sample_counter = calculate_new_average(
                self._mean_processing_time, new_sample, self._mean_processing_time_sample_counter
            )
            self._mean_processing_time = new_avg
            self._mean_processing_time_sample_counter = new_sample_counter

    special_field_types = ["regex_fields", "wildcard_fields", "sigma_fields", "ip_fields"]

    def __init__(self, filter_rule: FilterExpression):
        self.__class__.__hash__ = Rule.__hash__
        self.filter_str = str(filter_rule)
        self._filter = filter_rule
        self._special_fields = None
        self.file_name = None
        self._tests = []
        self.metrics = self.RuleMetrics(labels={"type": "rule"})

    @abstractmethod
    def __eq__(self, other: "Rule"):
        pass

    def __hash__(self) -> int:  # pylint: disable=function-redefined
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def filter(self):
        return self._filter

    @property
    def tests(self) -> list:
        return self._tests

    # pylint: enable=C0111

    @classmethod
    def create_rules_from_file(cls, path: str) -> list:
        """Create a rule from a file."""
        is_valid_json = is_json(path)
        rule_data = None
        with open(path, "r", encoding="utf8") as file:
            if is_valid_json:
                rule_data = json.load(file)
            else:
                rule_data = yaml.load_all(file)
            # needs to be executed in context manager of open, because
            # `yaml.load_all` returns a generator and read operation happens in
            # this list comprehension which leads to an I/O Error otherwise
            rules = [cls._create_from_dict(rule) for rule in rule_data]
        if len(rules) == 0:
            raise InvalidRuleDefinitionError("no rules in file")
        for rule in rules:
            rule.file_name = splitext(basename(path))[0]

        return rules

    @staticmethod
    def _create_from_dict(rule: dict):
        raise NotImplementedError

    @staticmethod
    def _check_rule_validity(
        rule: dict, *extra_keys: str, optional_keys: Optional[Set[str]] = None
    ):
        optional_keys = optional_keys if optional_keys else set()
        keys = [i for i in rule if i not in ["description"] + Rule.special_field_types]
        required_keys = ["filter"] + list(extra_keys)

        if not keys or set(keys) != set(required_keys):
            additional_keys = set(keys) - (set(keys).intersection(set(required_keys)))
            if not (optional_keys and additional_keys == optional_keys):
                raise InvalidRuleDefinitionError(f"Keys {keys} must be {required_keys}")

    def matches(self, document: dict) -> bool:
        """Check if a given document matches this rule."""
        return self._filter.matches(document)

    @classmethod
    def _create_filter_expression(cls, rule: dict) -> FilterExpression:
        special_fields = cls._get_special_fields_for_rule_matching(rule)
        return LuceneFilter.create(rule["filter"], special_fields)

    @staticmethod
    def _get_special_fields_for_rule_matching(rule: dict) -> dict:
        special_fields = {}

        for field_type in Rule.special_field_types:
            special_fields[field_type] = rule.get(field_type, [])
            if special_fields[field_type] and not (
                isinstance(special_fields[field_type], list) or special_fields[field_type] is True
            ):
                raise ValueError

        return special_fields
