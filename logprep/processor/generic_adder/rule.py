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
It contains the path or url to a file with a YML file that contains a dictionary of field names and
values that should be added to the document.
Instead of a path, a list of paths can be used to add multiple files.
All of those files must exist.
If a list is used, it is possible to tell the generic adder to only use the first existing
file by setting :code:`generic_adder.only_first_existing_file: true`.
In that case, only one file must exist.
Additions from :code:`generic_adder.add` and :code:`generic_adder.add_from_file` are
combined.

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

import copy
import os
import typing

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.converters import convert_from_dict
from logprep.util.getter import GetterFactory, HttpGetter, RefreshableGetter
from logprep.util.helper import DottedTemplate, FieldValue, get_dotted_field_value


@define(kw_only=True, frozen=True)
class AddFromUrlConfig:
    url: str = field(
        validator=[validators.instance_of(str), validators.matches_re(r"^https?://.+")]
    )

    target_field: str | None = field(
        default=None, validator=validators.optional(validators.instance_of(str))
    )

    target_field_mapping: dict[str, str] = field(
        validator=validators.deep_mapping(
            key_validator=validators.instance_of(str),
            value_validator=validators.instance_of(str),
        ),
        factory=dict,
    )

    def __attrs_post_init__(self) -> None:
        if not self.target_field and not self.target_field_mapping:
            raise ValueError("adding values from url requires target_field or target_field_mapping")


def _convert_add_from_url(
    value: AddFromUrlConfig | dict | None,
) -> AddFromUrlConfig | None:
    if value is None:
        return None

    return convert_from_dict(AddFromUrlConfig, value)


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
                value_validator=validators.instance_of((str, bool, list, dict, int, float)),
            ),
            default={},
        )
        """Contains a dictionary of field names and values that should be added.
        If dot notation is being used, then all fields on the path are being
        automatically created."""
        add_from_file: list[str] = field(
            validator=validators.deep_iterable(
                iterable_validator=validators.instance_of(list),
                member_validator=validators.instance_of(str),
            ),
            converter=lambda x: x if isinstance(x, list) else [x],
            factory=list,
            eq=False,
        )
        """Contains the path or url to YML file that contains a dictionary of field names
        and values that should be added to the document.
        Instead of a path, a list of paths can be used to add multiple files.
        All of those files must exist. For string format see :ref:`getters`

        .. security-best-practice::
           :title: Processor - Generic Adder Add From File Memory Consumption

           Be aware that all values of the remote file were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Generic Adder Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        add_from_url: AddFromUrlConfig | None = field(
            default=None,
            validator=validators.optional(validators.instance_of(AddFromUrlConfig)),
            converter=_convert_add_from_url,
        )

        only_first_existing_file: bool = field(
            validator=validators.instance_of(bool), default=False, eq=False
        )
        """If a list is used, it is possible to tell the generic adder to only use the
        first existing file by setting :code:`generic_adder.only_first_existing_file: true`.
        In that case, only one file must exist."""

        _base_add: dict = field(default={}, eq=False)
        """Stores original add fields (as provided in the config) for future refreshes of getters"""

        # pylint: enable=anomalous-backslash-in-string

        def _refresh_add(self):
            self.add = copy.deepcopy(self._base_add)
            self._add_from_path()

        def __attrs_post_init__(self):
            self._base_add = copy.deepcopy(self.add)

            if (self.add_from_file or self.add) and self.add_from_url is not None:
                raise ValueError(
                    "only one of add_from_file + add or add_from_url is allowed per GenericAdder rule"
                )

            if not self.add and not self.add_from_file and self.add_from_url is None:
                raise ValueError(
                    "one of add, add_from_file or add_from_url is neccessary per GenericAdder rule"
                )

            if (
                self.add_from_url is not None
                and self.add_from_url.target_field
                and self.add_from_url.target_field_mapping
            ):
                raise ValueError(
                    "only one of target_field or target_field_mapping is allowed per GenericAdder rule"
                )

            if (
                self.add_from_url is not None
                and not self.add_from_url.target_field
                and not self.add_from_url.target_field_mapping
            ):
                raise ValueError(
                    "one of target_field or target_field_mapping is neccessary per GenericAdder rule"
                )

            # Eagerly loaded from file
            for add_file in self.add_from_file:  # pylint: disable=not-an-iterable
                getter = GetterFactory.from_string(add_file)
                if isinstance(getter, RefreshableGetter):
                    # TODO: This never gets cleaned up, Memory leak on a lot of new generic adders / generic resolvers
                    getter.add_callback(f"generic_adder:{self.id}:{add_file}", self._refresh_add)
                self._add_from_path()

        def _add_from_path(self):
            """Reads add fields from file"""
            missing_files = []

            for add_file in self.add_from_file:
                try:
                    add_dict = GetterFactory.from_string(add_file).get_yaml()
                except FileNotFoundError:
                    missing_files.append(add_file)
                    continue
                if isinstance(add_dict, dict) and all(
                    isinstance(value, (str, bool, list, int, float)) for value in add_dict.values()
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

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self._dynamic_content: dict[str, FieldValue] = {}
        self._callback_tag = ""
        self._is_dynamic: bool = False
        self._dynamic_template: DottedTemplate
        self._dynamic_identifiers: tuple[str, ...] = ()

    def init_generic_adder(self, job_tag: str) -> None:
        self._callback_tag = job_tag

        config = typing.cast(GenericAdderRule.Config, self._config)
        if config.add_from_file or config.add:
            return

        assert config.add_from_url is not None

        base_template = DottedTemplate(config.add_from_url.url)
        resolved_template = DottedTemplate(base_template.safe_substitute({**os.environ}))
        self._dynamic_template = resolved_template
        self._dynamic_identifiers = tuple(resolved_template.get_identifiers())

        if len(self._dynamic_identifiers) > 0:
            self._is_dynamic = True

    def _dynamic_add_from_url(self, event: dict) -> dict[str, FieldValue]:
        config = typing.cast(GenericAdderRule.Config, self._config)

        assert config.add_from_url

        key_val = {
            identifier: get_dotted_field_value(event, identifier)
            for identifier in self._dynamic_identifiers
        }
        for identifier, val in key_val.items():
            if val is None:
                raise ValueError(
                    f"missing event field {identifier!r} for dynamic list comparison path"
                )
            if not isinstance(val, (str, int)):
                raise ValueError(
                    f"value for list comparison field {identifier!r} is not a scalar value"
                )
            pass

        dynamic_resolved = self._dynamic_template.substitute(key_val)
        content: FieldValue | None = None
        if dynamic_resolved not in self._dynamic_content:
            http_getter = GetterFactory.from_string(dynamic_resolved)
            assert isinstance(http_getter, HttpGetter)

            http_getter.keep_alive()

            content = http_getter.get_collection()
            self._dynamic_content[dynamic_resolved] = content

            tag = self._callback_tag

            http_getter.add_callback(
                tag,
                self._update_dynamic_content,
                deduplication_key=(tag, dynamic_resolved, id(self)),
                fnc_args=[http_getter, dynamic_resolved],
            )

            http_getter.add_cleanup_callback(
                tag,
                self._cleanup,
                deduplication_key=(tag, dynamic_resolved, id(self)),
                fnc_args=[dynamic_resolved],
            )

        else:
            RefreshableGetter.keep_alive_for_target(dynamic_resolved)
            content = self._dynamic_content[dynamic_resolved]

        items_to_add: dict[str, FieldValue] = {}

        if config.add_from_url.target_field:
            items_to_add[config.add_from_url.target_field] = content
        else:
            assert config.add_from_url.target_field_mapping is not None

            # TODO: Check this differently, what should this be?
            assert isinstance(content, dict)
            for (
                mapping_source_field,
                mapping_target_field,
            ) in config.add_from_url.target_field_mapping.items():
                # what should happen with missing fields? Right now None is skipped
                # change this to get_dotted_field_value_with_missing
                items_to_add[mapping_target_field] = get_dotted_field_value(
                    content, mapping_source_field
                )

        return items_to_add

    def _update_dynamic_content(self, http_getter: HttpGetter, resolved_uri: str):
        content = http_getter.get_collection()
        self._dynamic_content[resolved_uri] = content

    def _cleanup(self, resolved_uri: str):
        self._dynamic_content.pop(resolved_uri, None)

    def add(self, event: dict) -> dict:
        """Returns the fields to add"""
        config = typing.cast(GenericAdderRule.Config, self._config)

        if config.add_from_file or config.add:
            return config.add

        assert config.add_from_url is not None
        return self._dynamic_add_from_url(event)
