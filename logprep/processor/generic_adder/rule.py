# pylint: disable=anomalous-backslash-in-string
"""
Generic Adder
=============

The generic adder requires the additional field :code:`generic_adder`.
The field :code:`generic_adder.add` can be defined.
It contains a dictionary of field names and values that should be added.
If dot notation is being used, then all fields on the path are being automatically created.

In the following example, the field :code:`some.added.field` with the
value :code:`some added value` is being added.


..  code-block:: yaml
    :linenos:
    :caption: Example with add

    filter: add_generic_test
    generic_adder:
      add:
        some.added.field: some added value
    description: '...'

Alternatively, the additional field :code:`generic_adder.add_from_file` can be added.
It contains the path to a file with a YML file that contains a dictionary of field names and
values that should be added to the document.
Instead of a path, a list of paths can be used to add multiple files.
All of those files must exist.
If a list is used, it is possible to tell the generic adder to only use the first existing
file by setting :code:`generic_adder.only_first_existing_file: true`.
In that case, only one file must exist.

In the following example a dictionary with field names and values is loaded from the file
at :code:`PATH_TO_FILE_WITH_LIST`.
This dictionary is used like the one that can be defined via :code:`generic_adder.add`.

..  code-block:: yaml
    :linenos:
    :caption: Example with add_from_file

    filter: 'add_generic_test'
    generic_adder:
      add_from_file: PATH_TO_FILE_WITH_LIST
    description: '...'

In the following example two files are being used.

..  code-block:: yaml
    :linenos:
    :caption: Example with multiple files

    filter: 'add_generic_test'
    generic_adder:
      add_from_file:
        - PATH_TO_FILE_WITH_LIST
        - ANOTHER_PATH_TO_FILE_WITH_LIST
    description: '...'

In the following example two files are being used, but only the first existing file is being loaded.

..  code-block:: yaml
    :linenos:
    :caption: Example with multiple files and one loaded file

    filter: 'add_generic_test'
    generic_adder:
      only_first_existing_file: true
      add_from_file:
        - PATH_TO_FILE_THAT_DOES_NOT_EXIST
        - PATH_TO_FILE_WITH_LIST
    description: '...'

It is also possible to use a table from a MySQL database to add fields to an event.

..  code-block:: yaml
    :linenos:
    :caption: Example with a MySQL Table

    filter: '*'
    generic_adder:
      sql_table:
        event_source_field: source
        pattern: '([a-zA-Z0-9]+)_\S+'
        destination_field_prefix: nested.dict
    description: '...'
"""
# pylint: enable=anomalous-backslash-in-string

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
                value_validator=validators.instance_of((str, bool)),
            ),
            default={},
        )
        """Contains a dictionary of field names and values that should be added.
        If dot notation is being used, then all fields on the path are being
        automatically created."""
        add_from_file: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
            converter=lambda x: x if isinstance(x, list) else [x],
            factory=list,
            eq=False,
        )
        """Contains the path to a file with a YML file that contains a dictionary of field names
        and values that should be added to the document.
        Instead of a path, a list of paths can be used to add multiple files.
        All of those files must exist."""
        only_first_existing_file: bool = field(
            validator=validators.instance_of(bool), default=False, eq=False
        )
        """If a list is used, it is possible to tell the generic adder to only use the
        first existing file by setting :code:`generic_adder.only_first_existing_file: true`.
        In that case, only one file must exist."""
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
        # pylint: disable=anomalous-backslash-in-string
        """ sql config for generic adder (Optional)
        If a specified field in the table matches a condition, the remaining fields,
        except for the ID field, will be added to the event.
        The names of the new fields correspond to the column names in the MySQL table.
        This is mutually exclusive with the addition from a list.

        It can be defined via :code:`generic_adder.sql_table`.
        There :code:`generic_adder.sql_table.event_source_field` defines a field in the event that
        is being compared with values in the column of the MySQL table defined
        in the processor config. However, only a part of :code:`event_source_field` will
        be compared.
        Which part this is can be configured via :code:`generic_adder.sql_table.pattern`.
        This is a regex pattern with a capture group.
        The value in the capture group is being extracted and used for the comparison.
        :code:`generic_adder.sql_table.destination_field_prefix` can be used to prefix all added
        fields with a dotted path, creating a nested dictionary.

        In the following example the value of the field :code:`source` is being parsed
        with :code:`pattern: ([a-zA-Z0-9]+)_\S+`.
        It extracts the first alphanumerical string delimited by :code:`_`.
        I.e., :code:`Test0_foobarbaz` would extract :code:`test0`, which would be
        used for the comparison in the MySQL table.
        Since :code:`destination_field_prefix: nested.dict` is set,
        a newly added field :code:`FOO_NEW` would be placed under :code:`nested.dict.FOO_NEW`.
        """

        # pylint: enable=anomalous-backslash-in-string

        def __attrs_post_init__(self):
            if self.add_from_file:
                self._add_from_path()

        def _add_from_path(self):
            """Reads add fields from file"""
            missing_files = []
            existing_files = []

            for add_path in self.add_from_file:  # pylint: disable=not-an-iterable
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
