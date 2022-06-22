"""This module is used to add fields to documents via a list or a SQL table."""

import re
from os.path import isfile
from typing import Any, Union, List

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class GenericAdderRuleError(InvalidRuleDefinitionError):
    """Base class for GenericAdder rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GenericAdder rule ({message})")


class InvalidGenericAdderDefinition(GenericAdderRuleError):
    """Raise if GenericAdder definition invalid."""

    def __init__(self, definition):
        message = f"The following GenericAdder definition is invalid: {definition}"
        super().__init__(message)


class GenericAdderRule(Rule):
    """Check if documents match a filter and initialize the fields and values can be added."""

    def __init__(self, filter_rule: FilterExpression, generic_adder_cfg: dict):
        """Initialize base rule and prepare fields and values that will be added by this rule.

        Additions can either come from a list of key-value pairs or from a SQL table. If the SQL
        table is used, multiple values from a row in the table will be added.

        Parameters
        ----------
        filter_rule : FilterExpression
           Filter expression for the generic adder rule.
        generic_adder_cfg : dict
           Configuration for the generic adder rule.

        Raises
        ------
        InvalidGenericAdderDefinition
            Raises if the rule definition is invalid.

        """
        super().__init__(filter_rule)

        self._add = generic_adder_cfg.get("add", {})
        self._add_from_file = {}

        sql_table_cfg = generic_adder_cfg.get("sql_table", {})
        self._db_target = sql_table_cfg.get("event_source_field")
        raw_db_pattern = sql_table_cfg.get("pattern")
        self._db_pattern = re.compile(raw_db_pattern) if raw_db_pattern else None
        self._db_destination_prefix = sql_table_cfg.get("destination_field_prefix", "")

        only_first_existing = generic_adder_cfg.get("only_first_existing_file", False)

        add_paths = generic_adder_cfg.get("add_from_file")
        if add_paths is not None:
            self._add_from_path(only_first_existing, add_paths)

        self._add.update(self._add_from_file)

    def _add_from_path(self, only_first_existing: bool, add_paths: Union[str, List[str]]):
        """Reads add fields from file"""
        missing_files = []
        existing_files = []

        if isinstance(add_paths, str):
            add_paths = [add_paths]

        for add_path in add_paths:
            if not isfile(add_path):
                missing_files.append(add_path)
            else:
                existing_files.append(add_path)

        if only_first_existing:
            if existing_files:
                existing_files = existing_files[:1]
            else:
                raise InvalidGenericAdderDefinition(
                    f"At least one of the following files must " f"exist: '{missing_files}'"
                )
        else:
            if missing_files:
                raise InvalidGenericAdderDefinition(
                    f"The following required files do " f"not exist: '{missing_files}'"
                )

        for add_path in existing_files:
            with open(add_path, "r", encoding="utf8") as add_file:
                add_dict = yaml.load(add_file)
                if isinstance(add_dict, dict) and all(
                    isinstance(value, str) for value in add_dict.values()
                ):
                    self._add_from_file.update(add_dict)
                else:
                    error_msg = (
                        f"Additions file '{add_path}' must be a dictionary " f"with string values!"
                    )
                    raise InvalidGenericAdderDefinition(error_msg)

    def __eq__(self, other: "GenericAdderRule") -> bool:
        """Compare two generic adder rules.

        Parameters
        ----------
        other : GenericAdderRule
           Rule to be compared with current rule.

        Returns
        -------
        bool
            True if the properties of the rules are equal, False otherwise.

        """
        return all(
            [
                other.filter == self._filter,
                self._add == other.add,
                self._db_target == other.db_target,
                self._db_pattern == other.db_pattern,
                self._db_destination_prefix == other.db_destination_prefix,
            ]
        )

    # pylint: disable=C0111
    @property
    def add(self) -> dict:
        return self._add

    @property
    def add_from_file(self) -> dict:
        return self._add_from_file

    @property
    def db_target(self) -> str:
        return self._db_target

    @property
    def db_pattern(self) -> Any:
        return self._db_pattern

    @property
    def db_destination_prefix(self) -> str:
        return self._db_destination_prefix

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "GenericAdderRule":
        """Create a rule from a dictionary if the rule definition is valid.

        Parameters
        ----------
        rule : dict
           Rule in form of a dictionary.

        Returns
        -------
        GenericAdderRule
            Generic adder rule that has been created from a dict.

        """
        GenericAdderRule._check_rule_validity(rule, "generic_adder")
        GenericAdderRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return GenericAdderRule(filter_expression, rule["generic_adder"])

    @staticmethod
    def _check_if_valid(rule: dict):
        """Check if configuration for generic adder rule is valid and raise exceptions if it isn't.

        Parameters
        ----------
        rule : dict
           Rule in form of a dictionary.

        Raises
        ------
        InvalidGenericAdderDefinition
            Raises if the rule definition is invalid.

        """
        generic_adder_cfg = rule["generic_adder"]

        if not (
            "add_from_file" in generic_adder_cfg
            or "add" in generic_adder_cfg
            or "sql_table" in generic_adder_cfg
        ):
            raise InvalidGenericAdderDefinition(
                '"generic_adder" must contain "add" or ' '"add_from_file"!'
            )
        for field in ("add",):
            if generic_adder_cfg.get(field) and not isinstance(generic_adder_cfg[field], dict):
                raise InvalidGenericAdderDefinition(
                    f'"{field}" value "{generic_adder_cfg[field]}" is not a dict!'
                )
        for field in ("add_from_file",):
            if generic_adder_cfg.get(field):
                error_msg = (
                    f'"{field}" value "{generic_adder_cfg[field]}" is not a string or a'
                    f" list of strings!"
                )
                if not isinstance(generic_adder_cfg[field], (str, list)):
                    raise InvalidGenericAdderDefinition(error_msg)
                if isinstance(generic_adder_cfg[field], list) and not all(
                    isinstance(item, str) for item in generic_adder_cfg[field]
                ):
                    raise InvalidGenericAdderDefinition(error_msg)
