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
from collections.abc import Iterator, Sequence

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
class UriConfig:
    """
    Configuration for adding values loaded from an URI,
    which can be HTTP(S) URLs or file paths
    """

    uri: str = field(validator=validators.and_(validators.instance_of(str), validators.min_len(1)))
    """The URI to load values from.

    Environment variables and dotted event fields can be inserted with placeholders such as
    :code:`${LOGPREP_DATA_API}` and :code:`${tenant.id}`.
    """

    target_field: str | None = field(
        default=None,
        validator=validators.optional(
            validators.and_(validators.instance_of(str), validators.min_len(1))
        ),
    )
    """The dotted event field into which the complete response is written."""


def _convert_uri_config(
    value: str | dict | UriConfig | Sequence[str | dict | UriConfig],
) -> list[UriConfig]:
    values: Sequence[str | dict[str, object] | UriConfig]

    if isinstance(value, (str, dict, UriConfig)):
        values = [value]
    else:
        values = value

    return [
        UriConfig(uri=item) if isinstance(item, str) else convert_from_dict(UriConfig, item)
        for item in values
    ]


@define(kw_only=True)
class _UriSource:
    config: UriConfig
    template: DottedTemplate
    static_uri: str | None
    identifiers: Sequence[str]
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
            # Eq false because add_from_file gets normalized into add_from_uri
            # and should not affect equality
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

        add_from_uri: Sequence[UriConfig] = field(
            factory=list,
            converter=_convert_uri_config,
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(UriConfig),
            ),
        )
        """Configuration for loading values from URIs and adding them to the event.

        This is mutually exclusive with :attr:`add_from_file`.
        """

        content_field: str | None = field(
            default=None,
            validator=validators.optional(validators.instance_of(str)),
            converter=lambda x: x if x != "" else None,
        )
        """
        Optional JSON key used to extract the list values from loaded content.

        Example:
            Given the following JSON content:

            .. code-block:: json

               {
                   "content": ["Jane", "Julia"]
               }

            Set ``content_field`` to ``"content"`` to use the value of this key
            as the comparison list.

        Note:
            Setting ``content_field`` requires mapping-like JSON content. Non-JSON
            content, or JSON content that does not resolve to a mapping, fails with an
            error.

            An empty ``content_field`` is treated as unset, so the list is expected at
            the root of the JSON content.

            Examples:
                ``content_field: ""``
                    Is converted to ``None`` and reads the list from the JSON root.

                ``content_field: null``
                    Is treated as ``None`` and reads the list from the JSON root.

                ``content_field: "content"``
                    Reads the list from the ``"content"`` key of the JSON object.
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
                self.add_from_uri = _convert_uri_config(self.add_from_file)

            if self.only_first_existing_file and not self.add_from_file:
                raise ValueError(
                    "only_first_existing_file is only supported with deprecated add_from_file"
                )

            if not self.add and not self.add_from_uri:
                raise ValueError("one of add or add_from_uri must be configured")

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

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self._callback_tag: str | None = None
        self._uri_sources: list[_UriSource] = []

    def init_generic_adder(self, job_tag: str) -> None:
        """Initializes the generic adder and assignes the job_tag for callback cleanup"""
        self._callback_tag = job_tag

        if self.config.only_first_existing_file:
            self._init_first_existing_file()
            return

        for spec in self.config.add_from_uri:
            source = self._create_uri_source(spec)
            self._uri_sources.append(source)

            if not source.identifiers:
                self._init_static_source(source, raise_on_error=True)

    def _init_first_existing_file(self) -> None:
        missing_files: list[str] = []

        for config in self.config.add_from_uri:
            source = self._create_uri_source(config)
            if source.identifiers:
                raise InvalidRuleDefinitionError(
                    f"only_first_existing_file does not support event-dependent paths: {config!r}"
                )

            try:
                self._init_static_source(source, raise_on_error=True)
            except InvalidRuleDefinitionError as error:
                if isinstance(error.__cause__, FileNotFoundError):
                    missing_files.append(config.uri)
                    continue
                raise
            self._uri_sources.append(source)
            return
        raise InvalidRuleDefinitionError(f"None of the configured files exist: {missing_files!r}")

    def _create_uri_source(self, config: UriConfig) -> _UriSource:
        template = DottedTemplate(DottedTemplate(config.uri).safe_substitute(ENV_VARS))

        identifiers = template.get_identifiers()

        return _UriSource(
            config=config,
            template=template,
            identifiers=tuple(identifiers),
            static_uri=None if identifiers else template.substitute(),
        )

    def _init_static_source(self, source: _UriSource, raise_on_error: bool):
        assert source.static_uri is not None
        getter = GetterFactory.from_string(source.static_uri)

        assert self._callback_tag

        self._update_static_content(source, getter, source.static_uri)
        if source.error and raise_on_error:
            raise InvalidRuleDefinitionError(
                f"Could not load generic_adder URI {source.static_uri!r}: {source.error}"
            ) from source.error

        if isinstance(getter, RefreshableGetter):
            getter.add_callback(
                self._callback_tag,
                self._update_static_content,
                deduplication_key=(self._callback_tag, source.static_uri, id(source)),
                fnc_args=[source, getter, source.static_uri],
            )

    def _get_cached_or_dynamic_content(
        self, source: _UriSource, event: dict[str, FieldValue]
    ) -> FieldValue:
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

        resolved_uri = source.template.substitute(values)

        if resolved_uri in source.content_by_uri:
            RefreshableGetter.keep_alive_for_target(resolved_uri)
            return source.content_by_uri[resolved_uri]

        getter = GetterFactory.from_string(resolved_uri)
        if not isinstance(getter, RefreshableGetter):
            raise InvalidRuleDefinitionError(
                f"Dynamic file URIs are not supported, uri {resolved_uri!r}"
            )

        getter.keep_alive()
        content = self._fetch_and_cache_uri(source, getter, resolved_uri)

        assert self._callback_tag

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
            return self._get_cached_or_dynamic_content(source, event)

        assert source.static_uri
        return source.content_by_uri[source.static_uri]

    def _content_to_items_to_add(
        self, config: UriConfig, content: FieldValue
    ) -> dict[str, FieldValue]:
        if config.target_field is not None:
            return {config.target_field: content}

        if isinstance(content, dict):
            return content

        raise ValueError(f"""URI source {config.uri!r} without target_field must contain a mapping,
            got {type(content).__name__}""")

    def _fetch_and_cache_uri(self, source: _UriSource, getter: Getter, resolved_uri: str):
        content = getter.get_collection(content_field=self.config.content_field)
        source.content_by_uri[resolved_uri] = content
        return content

    def _update_static_content(self, source: _UriSource, getter: Getter, uri: str) -> None:
        try:
            self._fetch_and_cache_uri(source, getter, uri)
        except Exception as error:  # pylint: disable=broad-except
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
            self.mark_failed(ExceptionGroup("generic_adder URI loading failed", errors))

    def _cleanup(self, source: _UriSource, resolved_uri: str) -> None:
        source.content_by_uri.pop(resolved_uri, None)

    def additions(self, event: dict[str, FieldValue]) -> Iterator[dict[str, FieldValue]]:
        if self.config.add:
            yield self.config.add

        for source in self._uri_sources:
            content = self._content_for_source(source, event)
            yield self._content_to_items_to_add(source.config, content)

    def add(self, event: dict[str, FieldValue]) -> dict[str, FieldValue]:
        """Returns the fields to add"""
        return {key: value for items in self.additions(event) for key, value in items.items()}
