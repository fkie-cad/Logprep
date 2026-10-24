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

Examples for generic_adder:
---------------------------

.. datatemplate:import-module:: tests.unit.processor.generic_adder.test_generic_adder
   :template: testcase-renderer.tmpl
"""

# TODO(async-followup): Remove mypy ignore after completing the async migration.
# mypy: disable-error-code="override"
# pylint: disable=invalid-overridden-method

from collections.abc import AsyncIterator

from logprep.ng.abc.getter import Getter
from logprep.ng.util.getter import GetterFactory, RefreshableGetter
from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.generic_adder.rule import (
    GenericAdderRule as NonNGGenericAdderRule,
)
from logprep.processor.generic_adder.rule import (
    _UriSource,
)
from logprep.util.helper import (
    FieldValue,
    get_dotted_field_value,
)


class GenericAdderRule(NonNGGenericAdderRule):
    """Check if documents match a filter and initialize the fields and values can be added."""

    async def init_generic_adder(self, job_tag: str) -> None:
        """Initializes the generic adder and assigns the job tag for callback cleanup."""
        self._callback_tag = job_tag

        if self.config.only_first_existing_file:
            await self._init_first_existing_file()
            return

        for spec in self.config.add_from_uri:
            source = self._create_uri_source(spec)
            self._uri_sources.append(source)

            if not source.identifiers:
                await self._init_static_source(source, raise_on_error=True)

    async def _init_first_existing_file(self) -> None:
        """Initialize the first existing static file source."""
        missing_files: list[str] = []

        for config in self.config.add_from_uri:
            source = self._create_uri_source(config)

            if source.identifiers:
                raise InvalidRuleDefinitionError(
                    f"only_first_existing_file does not support event-dependent paths: {config!r}"
                )

            try:
                await self._init_static_source(source, raise_on_error=True)
            except InvalidRuleDefinitionError as error:
                if isinstance(error.__cause__, FileNotFoundError):
                    missing_files.append(config.uri)
                    continue
                raise

            self._uri_sources.append(source)
            return

        raise InvalidRuleDefinitionError(f"None of the configured files exist: {missing_files!r}")

    async def _init_static_source(
        self,
        source: _UriSource,
        raise_on_error: bool,
    ) -> None:
        """Initialize and register callbacks for a static URI source."""
        assert source.static_uri is not None

        getter = GetterFactory.from_string(source.static_uri)

        assert self._callback_tag

        await self._update_static_content(
            source,
            getter,
            source.static_uri,
        )

        if source.error and raise_on_error:
            raise InvalidRuleDefinitionError(
                f"Could not load generic_adder URI {source.static_uri!r}: {source.error}"
            ) from source.error

        if isinstance(getter, RefreshableGetter):
            getter.add_callback(
                self._callback_tag,
                self._update_static_content,
                deduplication_key=(
                    self._callback_tag,
                    source.static_uri,
                    id(source),
                ),
                fnc_args=[
                    source,
                    getter,
                    source.static_uri,
                ],
            )

    async def _get_cached_or_dynamic_content(
        self,
        source: _UriSource,
        event: dict[str, FieldValue],
    ) -> FieldValue:
        """Return cached content or asynchronously load content for a dynamic URI."""
        values = {
            identifier: get_dotted_field_value(event, identifier)
            for identifier in source.identifiers
        }

        for identifier, value in values.items():
            if value is None:
                raise ValueError(
                    f"missing event field {identifier!r} for dynamic generic adder URI"
                )

            if not isinstance(value, (str, int)):
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

        content = await self._fetch_and_cache_uri(
            source,
            getter,
            resolved_uri,
        )

        assert self._callback_tag

        key = (
            self._callback_tag,
            resolved_uri,
            id(source),
        )

        getter.add_callback(
            self._callback_tag,
            self._fetch_and_cache_uri,
            deduplication_key=key,
            fnc_args=[
                source,
                getter,
                resolved_uri,
            ],
        )

        getter.add_cleanup_callback(
            self._callback_tag,
            self._cleanup,
            deduplication_key=key,
            fnc_args=[
                source,
                resolved_uri,
            ],
        )

        return content

    async def _content_for_source(
        self,
        source: _UriSource,
        event: dict[str, FieldValue],
    ) -> FieldValue:
        """Return the content for a static or dynamic URI source."""
        if source.identifiers:
            return await self._get_cached_or_dynamic_content(
                source,
                event,
            )

        assert source.static_uri
        return source.content_by_uri[source.static_uri]

    async def _fetch_and_cache_uri(
        self,
        source: _UriSource,
        getter: Getter,
        resolved_uri: str,
    ) -> FieldValue:
        """Fetch URI content asynchronously and store it in the source cache."""
        content = await getter.get_collection(content_field=self.config.content_field)
        source.content_by_uri[resolved_uri] = content

        return content

    async def _update_static_content(
        self,
        source: _UriSource,
        getter: Getter,
        uri: str,
    ) -> None:
        """Refresh cached content and update the rule failure state."""
        try:
            await self._fetch_and_cache_uri(
                source,
                getter,
                uri,
            )
        except Exception as error:  # pylint: disable=broad-except
            source.error = error
        else:
            source.error = None

        self._recompute_failure_state()

    async def additions(
        self,
        event: dict[str, FieldValue],
    ) -> AsyncIterator[dict[str, FieldValue]]:
        """Yield configured and URI-loaded fields to add to the event."""
        if self.config.add:
            yield self.config.add

        for source in self._uri_sources:
            content = await self._content_for_source(
                source,
                event,
            )
            yield self._content_to_items_to_add(
                source.config,
                content,
            )

    async def add(
        self,
        event: dict[str, FieldValue],
    ) -> dict[str, FieldValue]:
        """Returns the fields to add"""
        result: dict[str, FieldValue] = {}

        async for items in self.additions(event):
            result.update(items)

        return result
