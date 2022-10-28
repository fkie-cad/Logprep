"""This module is used to add fields to documents via a list or a SQL table."""

import re
from os.path import isfile
from typing import Any
from attrs import define, field, validators

from ruamel.yaml import YAML

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

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for GenericAdderRule"""

        add: dict = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of(str),
            ),
            default={},
        )
        add_from_file: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
            converter=lambda x: x if isinstance(x, list) else [x],
            factory=list,
            eq=False,
        )
        only_first_existing_file: bool = field(
            validator=validators.instance_of(bool), default=False, eq=False
        )

        sql_table: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(
                        ["pattern", "event_source_field", "destination_field_prefix"]
                    ),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )

        def __attrs_post_init__(self):
            if self.add_from_file:
                self._add_from_path()

        def _add_from_path(self):
            """Reads add fields from file"""
            missing_files = []
            existing_files = []

            for add_path in self.add_from_file:
                if not isfile(add_path):
                    missing_files.append(add_path)
                else:
                    existing_files.append(add_path)

            if self.only_first_existing_file:
                if existing_files:
                    existing_files = existing_files[:1]
                else:
                    raise InvalidGenericAdderDefinition(
                        f"At least one of the following files must exist: '{missing_files}'"
                    )
            else:
                if missing_files:
                    raise InvalidGenericAdderDefinition(
                        f"The following required files do not exist: '{missing_files}'"
                    )

            for add_path in existing_files:
                with open(add_path, "r", encoding="utf8") as add_file:
                    add_dict = yaml.load(add_file)
                    if isinstance(add_dict, dict) and all(
                        isinstance(value, str) for value in add_dict.values()
                    ):
                        self.add = {**self.add, **add_dict}
                    else:
                        error_msg = (
                            f"Additions file '{add_path}' must be a dictionary with string values!"
                        )
                        raise InvalidGenericAdderDefinition(error_msg)

    @property
    def add(self) -> dict:
        """Returns the fields to add"""
        return self._config.add

    @property
    def db_target(self) -> str:
        """Returns the db target"""
        return self._config.sql_table.get("event_source_field")

    @property
    def db_pattern(self) -> Any:
        """Returns the db pattern"""
        raw_db_pattern = self._config.sql_table.get("pattern")
        return re.compile(raw_db_pattern) if raw_db_pattern else None

    @property
    def db_destination_prefix(self) -> str:
        """Returns the destination prefix"""
        return self._config.sql_table.get("destination_field_prefix", "")
