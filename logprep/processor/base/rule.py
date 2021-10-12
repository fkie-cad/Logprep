"""This module is the superclass for all rule classes."""

from typing import Set, Optional

from os.path import basename, splitext

from json import load
from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.filter.lucene_filter import LuceneFilter
from logprep.processor.base.exceptions import InvalidRuleDefinitionError

yaml = YAML(typ='safe', pure=True)


class Rule:
    """Check if documents match a filter and add labels them."""

    special_field_types = ['regex_fields', 'wildcard_fields', 'sigma_fields', 'ip_fields']

    def __init__(self, filter_rule: FilterExpression):
        self.filter_str = str(filter_rule)
        self._filter = filter_rule
        self._special_fields = None
        self.file_name = None
        self._tests = []

    def __eq__(self, other: 'Rule'):
        pass

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
        with open(path, 'r') as file:
            rule_data = list(yaml.load_all(file)) if path.endswith('.yml') else load(file)

        if not isinstance(rule_data, list):
            raise InvalidRuleDefinitionError('Rule file must contain a json or yml list.')

        rules = [cls._create_from_dict(rule) for rule in rule_data]
        for rule in rules:
            rule.file_name = splitext(basename(path))[0]

        return rules

    @staticmethod
    def _create_from_dict(rule: dict):
        raise NotImplementedError

    @staticmethod
    def _check_rule_validity(rule: dict, *extra_keys: str,
                             optional_keys: Optional[Set[str]] = None):
        optional_keys = optional_keys if optional_keys else set()
        keys = [i for i in rule if i not in ['description'] + Rule.special_field_types]
        required_keys = ['filter'] + list(extra_keys)

        if not keys or set(keys) != set(required_keys):
            additional_keys = set(keys) - (set(keys).intersection(set(required_keys)))
            if not (optional_keys and additional_keys == optional_keys):
                raise InvalidRuleDefinitionError('Keys {} must be {}.'.format(keys, required_keys))

    def matches(self, document: dict) -> bool:
        """Check if a given document matches this rule."""
        return self._filter.matches(document)

    @classmethod
    def _create_filter_expression(cls, rule: dict) -> FilterExpression:
        special_fields = cls._get_special_fields_for_rule_matching(rule)
        return LuceneFilter.create(rule['filter'], special_fields)

    @staticmethod
    def _get_special_fields_for_rule_matching(rule: dict) -> dict:
        special_fields = dict()

        for field_type in Rule.special_field_types:
            special_fields[field_type] = rule.get(field_type, list())
            if special_fields[field_type] and not (
                    isinstance(special_fields[field_type], list) or
                    special_fields[field_type] is True):
                raise ValueError

        return special_fields
