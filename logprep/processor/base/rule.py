"""
Basic Functionality
===================

How processors process log messages is defined via configurable rules.
Each rule contains a filter that is used to select log messages.
Other parameters within the rules define how certain log messages should be transformed.
Those parameters depend on the processor for which they were created.

Rule Files
==========

Rules are defined as YAML objects or JSON objects.
Rules can be distributed over different files or multiple rules can reside within one file.
Each file contains multiple YAML documents or a JSON array of JSON objects.
The YAML format is preferred, since it is a superset of JSON and has better readability.

Depending on the filter, a rule can trigger for different types of messages or just for specific log
messages.
In general, specific rules are being applied first.
It depends on the directory where the rule is located if it is considered specific or generic.

Further details can be found in the section for processors.

..  code-block:: yaml
    :linenos:
    :caption: Example structure of a YAML file with a rule for the labeler processor

    filter: 'command: execute'  # A comment
    labeler:
      label:
        action:
        - execute
    description: '...'

..  code-block:: yaml
    :linenos:
    :caption: Example structure of a YAML file containing multiple rules for the labeler processor

    filter: 'command: "execute something"'
    labeler:
      label:
        action:
        - execute
    description: '...'
    ---
    filter: 'command: "terminate something"'
    labeler:
      label:
        action:
        - execute
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Example structure of a JSON file with a rule for the labeler processor

    {
      "filter": "command: execute",
      "labeler": {
        "label": {
          "action": ["execute"]
        }
      }
      "description": "..."
    }

..  code-block:: json
    :linenos:
    :caption: Example structure of a JSON file containing multiple rules for the labeler processor

    [
      {
        "filter": "command: execute",
        "labeler": {
          "label": {
            "action": ["execute"]
          }
        }
        "description": "..."
      },
      {
        "filter": "command: execute",
        "labeler": {
          "label": {
            "action": ["execute"]
          }
        }
        "description": "..."
      }
    ]
"""

import json
from os.path import basename, splitext
from typing import List, Set, Optional, Dict

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

        description: str = field(validator=validators.instance_of(str), default="", eq=False)
        """A description for the Rule. This has only documentation character."""
        regex_fields: list = field(validator=validators.instance_of(list), factory=list)
        """It is possible to use regex expressions to match values.
        For this, the field name with the regex pattern in the rule filter must be added to the
        optional field :code:`regex_fields` in the rule definition."""

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
        """Custom tests for this rule."""
        tag_on_failure: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
            factory=list,
            converter=lambda x: list(set(x)),
        )
        """A list of tags which will be appended to the event on non critical errors,
        defaults to :code:`["_<rule_type>_failure"]`.
        Is currently only used by the Dissector and FieldManager.
        """

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

    special_field_types = ["regex_fields", "sigma_fields", "ip_fields", "tests", "tag_on_failure"]

    def __init__(self, filter_rule: FilterExpression, config: Config):
        if not isinstance(config, self.Config):
            raise InvalidRuleDefinitionError("config is not a Config class")
        if not config.tag_on_failure:
            config.tag_on_failure = [f"_{self.rule_type}_failure"]
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

    def __repr__(self) -> str:
        if hasattr(self, "_config"):
            return f"filter={self.filter}, {self._config}"
        return super().__repr__()

    # pylint: disable=C0111
    @property
    def filter(self):
        return self._filter

    @property
    def tests(self) -> list:
        return self._config.tests

    @property
    def failure_tags(self):
        return self._config.tag_on_failure

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
        cls.rule_type = camel_to_snake(cls.__name__.replace("Rule", ""))
        if not cls.rule_type:
            cls.rule_type = "rule"
        config = rule.get(cls.rule_type)
        if config is None:
            raise InvalidRuleDefinitionError(f"config not under key {cls.rule_type}")
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
