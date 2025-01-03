# pylint: disable=anomalous-backslash-in-string
"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

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

.. autoclass:: logprep.processor.generic_adder.rule.GenericAdderRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""
# pylint: enable=anomalous-backslash-in-string


from attrs import define, field, validators

from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.getter import GetterFactory


class GenericAdderRule(FieldManagerRule):
    """Check if documents match a filter and initialize the fields and values can be added."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for GenericAdderRule"""

        merge_with_target: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the values
        of the source fields.
        """
        add: dict = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of((str, bool, list)),
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
        All of those files must exist. For string format see :ref:`getters`"""
        only_first_existing_file: bool = field(
            validator=validators.instance_of(bool), default=False, eq=False
        )
        """If a list is used, it is possible to tell the generic adder to only use the
        first existing file by setting :code:`generic_adder.only_first_existing_file: true`.
        In that case, only one file must exist."""

        # pylint: enable=anomalous-backslash-in-string

        def __attrs_post_init__(self):
            if self.add_from_file:
                self._add_from_path()

        def _add_from_path(self):
            """Reads add fields from file"""
            missing_files = []
            for add_file in self.add_from_file:  # pylint: disable=not-an-iterable
                try:
                    add_dict = GetterFactory.from_string(add_file).get_yaml()
                except FileNotFoundError:
                    missing_files.append(add_file)
                    continue
                if isinstance(add_dict, dict) and all(
                    isinstance(value, str) for value in add_dict.values()
                ):
                    self.add = {**self.add, **add_dict}
                else:
                    error_msg = (
                        f"Additions file '{add_file}' must be a dictionary with string values!"
                    )
                    raise InvalidRuleDefinitionError(error_msg)
                if self.only_first_existing_file:
                    break
            if missing_files and not self.only_first_existing_file:
                raise InvalidRuleDefinitionError(
                    f"The following required files do not exist: '{missing_files}'"
                )

    @property
    def add(self) -> dict:
        """Returns the fields to add"""
        return self._config.add
