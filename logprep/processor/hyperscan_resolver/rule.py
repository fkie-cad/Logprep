"""
Hyperscan Resolver
==================

The hyperscan resolver requires the additional field :code:`hyperscan_resolver`.
It works similarly to the generic resolver, but utilized hyperscan to process resolve lists.

For further information see: :ref:`generic-resolver-rule`

The hyperscan resolver uses the
`Python Hyperscan library <https://python-hyperscan.readthedocs.io/en/latest/>`_
to check regex patterns.
By default, the compiled Hyperscan databases will be stored persistently in the directory
specified in the :code:`pipeline.yml`.
The field :code:`store_db_persistent` can be used to configure
if a database compiled from a rule's :code:`resolve_list` should be stored persistently.

"""
import re
from typing import Tuple
from attrs import define, field, validators

from ruamel.yaml import YAML

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError
from logprep.processor.generic_resolver.rule import GenericResolverRule

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

    @define(kw_only=True)
    class Config(GenericResolverRule.Config):
        """RuleConfig for HyperscanResolver"""

        # Not used to check for equality, since it's results are reflected in resolve_list
        resolve_from_file: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(["path", "pattern"]),
                    value_validator=validators.instance_of(str),
                ),
            ],
            converter=lambda x: {"path": x, "pattern": ""} if isinstance(x, str) else x,
            factory=dict,
            eq=False,
        )
        """A YML file with a resolve list and an optional regex pattern can
        be used to resolve values.
        For this, either a field :code:`resolve_from_file` with a path to a resolve list
        file must be added or dictionary field :code:`resolve_from_file` with the subfields
        :code:`path` and :code:`pattern`.
        Using the :code:`pattern` option allows to define one regex pattern that
        can be used on all entries within a resolve list instead of having
        to write a regex pattern for each entry in the list."""
        store_db_persistent: bool = field(validator=validators.instance_of(bool), default=False)
        """Can be used to configure if a database compiled from
        a rule's :code:`resolve_list` should be stored persistently."""

        def __attrs_post_init__(self):
            if self.resolve_from_file:
                self._init_resolve_from_file()

        def _init_resolve_from_file(self):
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
            self.resolve_list = {**self.resolve_list, **add_dict}

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
                            replaced_pattern = HyperscanResolverRule.Config._replace_pattern(
                                mapping, pattern
                            )
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
                resolve_file_path = self.resolve_from_file
            elif isinstance(self.resolve_from_file, dict):
                resolve_file_path = self.resolve_from_file.get("path")
                pattern = self.resolve_from_file.get("pattern")
                if resolve_file_path is None or pattern is None:
                    raise InvalidHyperscanResolverDefinition(
                        f"Parameter 'resolve_from_file' ({self.resolve_from_file}) must be "
                        f"either a dictionary with path and pattern or a string containing a path!"
                    )
            return pattern, resolve_file_path

    # pylint: disable=C0111
    @property
    def field_mapping(self) -> dict:
        return self._config.field_mapping

    @property
    def resolve_list(self) -> dict:
        return self._config.resolve_list

    @property
    def resolve_from_file(self) -> str:
        return self._config.resolve_from_file

    @property
    def append_to_list(self) -> bool:
        return self._config.append_to_list

    @property
    def store_db_persistent(self) -> bool:
        return self._config.store_db_persistent

    # pylint: enable=C0111
