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
If a list is used, it is possible to tell the |PROCESSOR_NAME| to only use the first existing
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

import typing
from collections.abc import Sequence

from attrs import define, field, validators

from logprep.abc.getter import Getter
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import InvalidRuleDefinitionError, Rule
from logprep.util.converters import convert_from_dict
from logprep.util.environ import ENV_VARS
from logprep.util.getter import GetterFactory, RefreshableGetter
from logprep.util.helper import (
    DottedTemplate,
    FieldValue,
    get_dotted_field_value,
)


@define(kw_only=True, frozen=True)
class UriTargetConfig:
    """Configuration for adding values loaded from an HTTP(S) URL."""

    uri: str = field(validator=validators.and_(validators.instance_of(str), validators.min_len(1)))
    """The URL to load values from.

    Environment variables and dotted event fields can be inserted with placeholders such as
    :code:`${TENANT}` and :code:`${tenant.id}`.
    """

    target_field: str = field(
        validator=validators.and_(validators.instance_of(str), validators.min_len(1))
    )
    """The dotted event field into which the complete response is written."""


UriSpec = str | UriTargetConfig


def _convert_uri_specs(
    value: UriSpec | dict | Sequence[UriSpec | dict],
) -> tuple[UriSpec, ...]:
    if isinstance(value, (str, UriTargetConfig, dict)):
        values: tuple[UriSpec | dict, ...] = (value,)
    else:
        values = tuple(value)

    return tuple(
        convert_from_dict(UriTargetConfig, item) if isinstance(item, dict) else item
        for item in values
    )


@define(kw_only=True)
class _UriSource:
    spec: UriSpec
    template: DottedTemplate
    identifiers: tuple[str, ...]
    content_by_uri: dict[str, FieldValue] = field(factory=dict)
    error: Exception | None = None


class GenericAdderRule(Rule):
    """Check if documents match a filter and initialize the fields and values can be added."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for GenericAdderRule"""

        overwrite_target: bool = field(validator=validators.instance_of(bool), default=False)
        """Overwrite the target field value if exists. Defaults to :code:`False`"""

        merge_with_target: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the values
        of the source fields.
        """

        add: dict = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of((str, bool, list, dict, int, float)),
            ),
            factory=dict,
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
            # Eq false in this case means that this is not taken into account when comparing two Configs,
            # that is neccessary in this case because on init this will be loaded into add,
            # and when comparing two rules, we dont care if whats to add came from a file or is written inline
            # but we do care if whatever gets added is the same
            eq=False,
        )
        """Contains the path or url to YML file that contains a dictionary of field names
        and values that should be added to the document.
        Instead of a path, a list of paths can be used to add multiple files.
        All of those files must exist. For string format see :ref:`getters`

        .. security-best-practice::
           :title: |PROCESSOR| - Add From File Memory Consumption

           Be aware that all values of the remote file were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: |PROCESSOR| - Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        add_from_uri: tuple[UriSpec, ...] = field(
            factory=tuple,
            converter=_convert_uri_specs,
            validator=validators.deep_iterable(
                iterable_validator=validators.instance_of(tuple),
                member_validator=validators.instance_of((str, UriTargetConfig)),
            ),
            # Explicitly set it to true here to show the difference between this and add_from_file
            eq=True,
        )
        """Configuration for loading values from an HTTP(S) URL and adding them to the event.

        This is mutually exclusive with :attr:`add_from_file`.
        """

        only_first_existing_file: bool = field(
            validator=validators.instance_of(bool), default=False, eq=False
        )
        """If a list is used, it is possible to tell the generic adder to only use the
        first existing file by setting :code:`generic_adder.only_first_existing_file: true`.
        In that case, only one file must exist."""

        def __attrs_post_init__(self):
            if self.add_from_file and self.add_from_uri:
                raise ValueError(
                    "Deprecated add_from_file and new add_from_uri cannot both be configured"
                )

            if self.add_from_file:
                self.add_from_uri = tuple(self.add_from_file)

            if self.only_first_existing_file and not self.add_from_file:
                raise ValueError(
                    "only_first_existing_file is only supported with deprecated add_from_file"
                )

            if not self.add and not self.add_from_uri:
                raise ValueError("one of add or add_from_uri must be configured")

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self._callback_tag: str | None = None
        self._uri_sources: list[_UriSource] = []

    def init_generic_adder(self, job_tag: str) -> None:
        self._callback_tag = job_tag
        self._uri_sources.clear()

        if self.config.only_first_existing_file:
            self._init_first_existing_file()
            return

        for spec in self.config.add_from_uri:
            source = self._create_uri_source(spec)
            self._uri_sources.append(source)

            if not source.identifiers:
                self._init_static_source(source)

    def _init_first_existing_file(self) -> None:
        missing_files: list[str] = []

        for spec in self.config.add_from_uri:
            assert isinstance(spec, str)

            source = self._create_uri_source(spec)
            if source.identifiers:
                raise InvalidRuleDefinitionError(
                    f"only_first_existing_file does not support event-dependent paths: {spec!r}"
                )

            self._uri_sources.append(source)

            try:
                self._init_static_source(source)
                if source.error is not None:
                    raise InvalidRuleDefinitionError(
                        f"Could not load generic-adder URI {spec!r}: {source.error}"
                    ) from source.error
            except InvalidRuleDefinitionError as error:
                self._uri_sources.pop()

                if isinstance(error.__cause__, FileNotFoundError):
                    missing_files.append(spec)
                    continue

                raise

            return

        raise InvalidRuleDefinitionError(f"None of the configured files exist: {missing_files!r}")

    def _create_uri_source(self, spec: UriSpec) -> _UriSource:
        uri = spec.uri if isinstance(spec, UriTargetConfig) else spec
        template = DottedTemplate(DottedTemplate(uri).safe_substitute(ENV_VARS))

        return _UriSource(
            spec=spec, template=template, identifiers=tuple(template.get_identifiers())
        )

    def _init_static_source(self, source: _UriSource):
        resolved_uri = source.template.substitute()
        getter = GetterFactory.from_string(resolved_uri)

        if isinstance(getter, RefreshableGetter):
            self._update_static_content(source, getter, resolved_uri)
            getter.add_callback(
                self._callback_tag,
                self._update_static_content,
                deduplication_key=(self._callback_tag, resolved_uri, id(source)),
                fnc_args=[source, getter, resolved_uri],
            )
            return

        try:
            self._fetch_and_cache_uri(source, getter, resolved_uri)
        except (FileNotFoundError, ValueError) as error:
            raise InvalidRuleDefinitionError(
                f"Could not load generic-adder URI {resolved_uri!r}: {error}"
            ) from error

    @property
    def overwrite_target(self) -> bool:
        """Returns the nested config overwrite_target"""
        return self.config.overwrite_target

    @property
    def merge_with_target(self) -> bool:
        """Returns the nested config merge_with_target"""
        return self.config.merge_with_target

    @property
    def config(self) -> Config:
        """Return typed config"""
        return typing.cast(GenericAdderRule.Config, self._config)

    def _dynamic_content(self, source: _UriSource, event: dict[str, FieldValue]) -> FieldValue:
        values = {
            identifier: get_dotted_field_value(event, identifier)
            for identifier in source.identifiers
        }
        for identifier, val in values.items():
            if val is None:
                raise ValueError(
                    f"missing event field {identifier!r} for dynamic generic adder URI"
                )
            if not isinstance(val, (str, int)):
                raise ValueError(
                    f"value for generic adder field {identifier!r} is not a scalar value"
                )
            pass

        resolved_uri = source.template.substitute(values)

        if resolved_uri in source.content_by_uri:
            RefreshableGetter.keep_alive_for_target(resolved_uri)
            return source.content_by_uri[resolved_uri]

        getter = GetterFactory.from_string(resolved_uri)
        if not isinstance(getter, RefreshableGetter):
            return getter.get_collection()

        getter.keep_alive()
        content = self._fetch_and_cache_uri(source, getter, resolved_uri)

        key = (self._callback_tag, resolved_uri, id(source))

        getter.add_callback(
            self._callback_tag,
            self._fetch_and_cache_uri,
            deduplication_key=key,
            fnc_args=[source, getter, resolved_uri],
        )

        getter.add_cleanup_callback(
            self._callback_tag,
            self._cleanup,
            deduplication_key=key,
            fnc_args=[source, resolved_uri],
        )

        return content

    def _content_for_source(self, source: _UriSource, event: dict[str, FieldValue]) -> FieldValue:
        if source.identifiers:
            return self._dynamic_content(source, event)

        resolved_uri = source.template.substitute()
        return source.content_by_uri[resolved_uri]

    def _content_to_items_to_add(self, uri: UriSpec, content: FieldValue) -> dict[str, FieldValue]:
        if isinstance(uri, UriTargetConfig):
            return {uri.target_field: content}

        if isinstance(content, dict):
            return dict(content)

        raise ValueError(
            f"URI source {uri!r} without target_field must contain a mapping, got {type(content).__name__}"
        )

    def _fetch_and_cache_uri(self, source: _UriSource, getter: Getter, resolved_uri: str):
        content = getter.get_collection()

        self._content_to_items_to_add(source.spec, content)
        source.content_by_uri[resolved_uri] = content
        return content

    def _update_static_content(self, source: _UriSource, getter: Getter, uri: str) -> None:
        try:
            self._fetch_and_cache_uri(source, getter, uri)
        except Exception as error:
            source.error = error
        else:
            source.error = None

        self._recompute_failure_state()

    def _recompute_failure_state(self) -> None:
        errors = [source.error for source in self._uri_sources if source.error is not None]

        if not errors:
            self.clear_failed()
        elif len(errors) == 1:
            self.mark_failed(errors[0])
        else:
            self.mark_failed(ExceptionGroup("generic-adder URI loading failed", errors))

    def _cleanup(self, source: _UriSource, resolved_uri: str) -> None:
        source.content_by_uri.pop(resolved_uri, None)

    def add(self, event: dict) -> dict:
        """Returns the fields to add"""
        items_to_add: dict[str, FieldValue] = dict(self.config.add)

        for source in self._uri_sources:
            content = self._content_for_source(source, event)
            items_to_add.update(self._content_to_items_to_add(source.spec, content))

        return items_to_add
