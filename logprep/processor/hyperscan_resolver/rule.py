"""This module is used to resolve field values from documents via a list."""
import re
from typing import Tuple

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class HyperscanResolverRuleError(InvalidRuleDefinitionError):
    """Base class for HyperscanResolver rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"HyperscanResolver rule ({message}): ")


class InvalidHyperscanResolverDefinition(HyperscanResolverRuleError):
    """Raise if HyperscanResolver definition invalid."""

    def __init__(self, definition):
        message = f"The following HyperscanResolver definition is invalid: {definition}"
        super().__init__(message)


class HyperscanResolverRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, hyperscan_resolver_cfg: dict):
        super().__init__(filter_rule)

        self._field_mapping = hyperscan_resolver_cfg.get("field_mapping")
        self._resolve_list = hyperscan_resolver_cfg.get("resolve_list", {})
        self._resolve_from_file = hyperscan_resolver_cfg.get("resolve_from_file", None)
        self._append_to_list = hyperscan_resolver_cfg.get("append_to_list", False)
        self._store_db_persistent = hyperscan_resolver_cfg.get("store_db_persistent", False)

        self._init_resolve_from_file()

    def _init_resolve_from_file(self):
        if self._resolve_from_file:
            pattern, resolve_file_path = self._get_resolve_file_path_and_pattern()
            try:
                with open(resolve_file_path, "r", encoding="utf8") as add_file:
                    add_dict = yaml.load(add_file)

                    if isinstance(add_dict, dict) and all(
                        isinstance(value, str) for value in add_dict.values()
                    ):
                        self._add_dict_to_resolve_list(add_dict, pattern)
                    else:
                        raise InvalidHyperscanResolverDefinition(
                            f"Additions file '{self.resolve_from_file} must be a dictionary with "
                            f"string values!"
                        )
            except FileNotFoundError as error:
                raise InvalidHyperscanResolverDefinition(
                    f"Additions file '{self.resolve_from_file}' not found!"
                ) from error

    def _add_dict_to_resolve_list(self, add_dict: dict, pattern: str):
        if pattern:
            add_dict = self._replace_patterns_in_resolve_dict(add_dict, pattern)
        self._resolve_list.update(add_dict)

    @staticmethod
    def _replace_patterns_in_resolve_dict(add_dict: dict, pattern: str):
        replaced_add_dict = {}
        for key, value in add_dict.items():
            matches = re.match(pattern, key)
            if matches:
                mapping = matches.group("mapping")
                if mapping:
                    match_key = re.match(f"^{pattern}$", key)
                    if match_key:
                        replaced_pattern = HyperscanResolverRule._replace_pattern(mapping, pattern)
                        replaced_add_dict[replaced_pattern] = value
        add_dict = replaced_add_dict
        return add_dict

    @staticmethod
    def _replace_pattern(mapping: str, pattern: str) -> str:
        first_pos = pattern.find("(?P<mapping>")
        last_pos = first_pos
        bracket_cnt = 0
        escape_cnt = 0
        for char in pattern[first_pos:]:
            if char == "\\":
                escape_cnt += 1
            elif char == "(":
                if escape_cnt % 2 == 0:
                    bracket_cnt += 1
                escape_cnt = 0
            elif char == ")":
                if escape_cnt % 2 == 0:
                    bracket_cnt -= 1
                escape_cnt = 0
            else:
                escape_cnt = 0
            last_pos += 1
            if bracket_cnt <= 0:
                break
        replaced_pattern = pattern[:first_pos] + re.escape(mapping) + pattern[last_pos:]
        return replaced_pattern

    def _get_resolve_file_path_and_pattern(self) -> Tuple[str, str]:
        resolve_file_path = None
        pattern = None
        if isinstance(self.resolve_from_file, str):
            resolve_file_path = self._resolve_from_file
        elif isinstance(self.resolve_from_file, dict):
            resolve_file_path = self._resolve_from_file.get("path")
            pattern = self._resolve_from_file.get("pattern")
            if resolve_file_path is None or pattern is None:
                raise InvalidHyperscanResolverDefinition(
                    f"Parameter 'resolve_from_file' ({self.resolve_from_file}) must be "
                    f"either a dictionary with path and pattern or a string containing a path!"
                )
        return pattern, resolve_file_path

    def __eq__(self, other: "HyperscanResolverRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                self._field_mapping == other.field_mapping,
                self._resolve_list == other.resolve_list,
                self._append_to_list == other.append_to_list,
            ]
        )

    def __hash__(self) -> int:
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def field_mapping(self) -> dict:
        return self._field_mapping

    @property
    def resolve_list(self) -> dict:
        return self._resolve_list

    @property
    def resolve_from_file(self) -> str:
        return self._resolve_from_file

    @property
    def append_to_list(self) -> bool:
        return self._append_to_list

    @property
    def store_db_persistent(self) -> bool:
        return self._store_db_persistent

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "HyperscanResolverRule":
        HyperscanResolverRule._check_rule_validity(rule, "hyperscan_resolver")
        HyperscanResolverRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return HyperscanResolverRule(filter_expression, rule["hyperscan_resolver"])

    @staticmethod
    def _check_if_valid(rule: dict):
        hyperscan_resolver_cfg = rule["hyperscan_resolver"]
        for field in ("field_mapping",):
            if not isinstance(hyperscan_resolver_cfg[field], dict):
                raise InvalidHyperscanResolverDefinition(
                    f'"{field}" value "{hyperscan_resolver_cfg[field]}" is not a string!'
                )
