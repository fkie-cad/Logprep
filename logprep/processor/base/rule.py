"""This module is the superclass for all rule classes."""

import json
from os.path import basename, splitext
from typing import List, Set, Optional, Union, Dict

from attrs import define, field, validators

from ruamel.yaml import YAML

from logprep.metrics.metric import Metric, calculate_new_average
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.json_handling import is_json
from logprep.util.helper import camel_to_snake

yaml = YAML(typ="safe", pure=True)


class Rule:
    """Check if documents match a filter and add labels them."""

    @define(kw_only=True)
    class Config:
        """Config for Rule"""

        source_field: str = field(validator=validators.instance_of(str), default="")
        target_field: str = field(validator=validators.instance_of(str), default="")
        delete_source_field: str = field(validator=validators.instance_of(bool), default=False)
        description: str = field(validator=validators.instance_of(str), default="", eq=False)
        ip_fields: list = field(validator=validators.instance_of(list), factory=list)
        regex_fields: list = field(validator=validators.instance_of(list), factory=list)
        wildcard_fields: list = field(validator=validators.instance_of(list), factory=list)
        sigma_fields: Union[list, bool] = field(
            validator=validators.instance_of((list, bool)), factory=list
        )
        tests: List[Dict[str, str]] = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(
                    member_validator=validators.instance_of(dict),
                    iterable_validator=validators.instance_of(list),
                ),
                validators.deep_iterable(
                    member_validator=validators.deep_mapping(
                        key_validator=validators.instance_of(str),
                        value_validator=validators.instance_of(str),
                    )
                ),
            ],
            converter=lambda x: [x] if isinstance(x, dict) else x,
            factory=list,
        )

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

    special_field_types = ["regex_fields", "wildcard_fields", "sigma_fields", "ip_fields", "tests"]

    def __init__(self, filter_rule: FilterExpression, config: Config):
        if not isinstance(config, self.Config):
            raise InvalidRuleDefinitionError("config is not a Config class")
        self.__class__.__hash__ = Rule.__hash__
        self.filter_str = str(filter_rule)
        self._filter = filter_rule
        self._special_fields = None
        self.file_name = None
        self.metrics = self.RuleMetrics(labels={"type": "rule"})
        self._config = config

    def __eq__(self, other: "Rule") -> bool:
        return all([other.filter == self._filter, other._config == self._config])

    def __hash__(self) -> int:  # pylint: disable=function-redefined
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def filter(self):
        return self._filter

    @property
    def tests(self) -> list:
        return self._config.tests

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

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        """normalizes rule dict before create rule config object"""

    @classmethod
    def _create_from_dict(cls, rule: dict) -> "Rule":
        cls.normalize_rule_dict(rule)
        filter_expression = Rule._create_filter_expression(rule)
        rule_type = camel_to_snake(cls.__name__.replace("Rule", ""))
        if not rule_type:
            rule_type = "rule"
        config = rule.get(rule_type)
        if config is None:
            raise InvalidRuleDefinitionError(f"config not under key {rule_type}")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config.update({"description": rule.get("description", "")})
        for special_field in cls.special_field_types:
            special_field_value = rule.get(special_field)
            if special_field_value is not None:
                config.update({special_field: special_field_value})
        config = cls.Config(**config)
        return cls(filter_expression, config)

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
        if "filter" not in rule:
            raise InvalidRuleDefinitionError("no filter defined")
        return LuceneFilter.create(rule["filter"], special_fields)

    @staticmethod
    def _get_special_fields_for_rule_matching(rule: dict) -> dict:
        special_fields = {}

        for field_type in Rule.special_field_types:
            if field_type == "tests":
                continue
            special_fields[field_type] = rule.get(field_type, [])
            if special_fields[field_type] and not (
                isinstance(special_fields[field_type], list) or special_fields[field_type] is True
            ):
                raise ValueError

        return special_fields
