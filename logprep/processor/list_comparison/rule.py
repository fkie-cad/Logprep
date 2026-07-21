"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The list comparison enricher requires the additional field :code:`list_comparison`.
The mandatory keys under :code:`list_comparison` are :code:`source_fields`
(as list with one element) and :code:`target_field`. Former
is used to identify the field which is to be checked against the provided lists.
And the latter is used to define the parent field where the results should
be written to. Both fields can be dotted subfields.

Additionally, a list or array of lists can be provided underneath the
required field :code:`list_file_paths`.

In the following example, the field :code:`user_agent` will be checked against the provided list
(:code:`priviliged_users.txt`).
Assuming that the value :code:`non_privileged_user` will match the provided list,
the result of the list comparison (:code:`in_list`) will be added to the
target field :code:`List_comparison.example`.

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to compare a single field against a provided list.

    filter: 'user_agent'
    list_comparison:
        source_fields: ['user_agent']
        target_field: 'List_comparison.example'
        list_file_paths:
            - lists/privileged_users.txt
    description: '...'

.. note::

    Currently, it is not possible to check in more than one :code:`source_field` per rule.

.. autoclass:: logprep.processor.list_comparison.rule.ListComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import functools
import logging
import os.path
from abc import ABC, abstractmethod
from collections.abc import Generator
from enum import Enum, auto
from string import Template
from typing import TypeAlias

from attrs import define, field, validators

from logprep.abc.getter import Getter
from logprep.factory_error import InvalidConfigurationError
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.environ import ENV_VARS
from logprep.util.getter import (
    GetterFactory,
    RefreshableGetter,
)
from logprep.util.helper import DottedTemplate, get_dotted_field_value

logger = logging.getLogger()

ListName: TypeAlias = str
ListContent: TypeAlias = set


class ContentFailure(Enum):
    """Sentinel type for indicating missing fields."""

    CONTENT_FAILURE = auto()


CONTENT_FAILURE = ContentFailure.CONTENT_FAILURE  # pylint: disable=invalid-name
"""Sentinel value for indicating failed content retrievals"""


@define(kw_only=True)
class _CompareSet(ABC):
    name: ListName

    @abstractmethod
    def update_content(self, uri: str, content: ListContent | None):
        """Updates the cached and post-processed content"""


@define(kw_only=True)
class _StaticCompareSet(_CompareSet):
    content: ListContent | None
    error: Exception | None = field(default=None)

    def update_content(self, _, content: ListContent | None):
        self.content = content


@define(kw_only=True)
class _DynamicCompareSet(_CompareSet):
    uri_template: DottedTemplate
    uri_to_content: dict[str, ListContent] = field(factory=dict)

    def update_content(self, uri: str, content: ListContent | None):
        if content is None:
            self.remove_content(uri)
        else:
            self.uri_to_content[uri] = content

    def remove_content(self, uri: str):
        """Remove the cached contents for a specific uri"""
        self.uri_to_content.pop(uri, None)


class ListComparisonRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for ListComparisonRule"""

        list_file_paths: list[str] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str)),
            factory=list,
        )
        """List of files. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: Processor - List Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - List Comparison list file paths Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        list_paths: dict[ListName, str] = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(ListName),
                value_validator=validators.instance_of(str),
                mapping_validator=validators.instance_of(dict),
            ),
            factory=dict,
        )
        """
        Mapping for configuring list paths with representative names.
        Keys represent the names on which results will be reported.
        Values represent the paths which populates `${LOGPREP_LIST}`.

        Example:

        ..  code-block:: yaml

            list_paths:
                BLACKLISTED_HOSTS: blacklists/malicious_hosts
            list_search_base_path: http://example.tld/api/${LOGPREP_LIST}


        .. security-best-practice::
           :title: Processor - List Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - List Comparison list file paths Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        list_search_base_path: str | None = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )
        """
        Base path used to resolve this rule's relative ``list_file_paths``.

        If unset, the processor-level ``list_search_base_path`` is used. A base path must
        be configured either on the rule or on the processor.

        The value may use getter syntax and ``string.Template`` placeholders.
        Environment variables and ``${LOGPREP_LIST}`` are resolved during setup. For
        HTTP(S) paths, unresolved placeholders are resolved from event fields during
        processing.
        """
        mapping: dict = field(default={}, init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
        content_field: str | None = field(
            validator=validators.optional(validators.instance_of(str)),
            converter=lambda value: None if value == "" else value,
            default=None,
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

        def __attrs_post_init__(self):
            if self.list_file_paths and self.list_paths:
                raise ValueError("`list_file_paths` and `list_paths` must not both be specified")

        @functools.cached_property
        def named_paths(self) -> dict[ListName, str]:
            """
            Adapter property unifying access to legacy `list_file_paths` and `list_paths`
            """
            if self.list_paths:
                return self.list_paths
            # legacy: path name is the path itself
            return {path: path for path in self.list_file_paths}

    def __init__(
        self,
        filter_rule: FilterExpression,
        config: "ListComparisonRule.Config",
        processor_name: str,
    ):
        super().__init__(filter_rule, config, processor_name)
        self._config: ListComparisonRule.Config = self._config
        self._callback_tag = ""
        self.compare_set_names = self._config.named_paths.keys()
        self._static_sets: list[_StaticCompareSet] = []
        self._dynamic_sets: list[_DynamicCompareSet] = []
        self._all_dynamic_identifiers: tuple[str, ...] = ()

    def _get_list_search_base_path(self, list_search_base_path: str | None) -> str:
        if self._config.list_search_base_path:
            return self._config.list_search_base_path
        if list_search_base_path:
            self._config.list_search_base_path = list_search_base_path
            return list_search_base_path

        raise InvalidConfigurationError(
            "list_search_base_path must be set either in the processor config or in the rule"
        )

    def init_list_comparison(
        self,
        callback_tag: str,
        list_search_base_path: str | None = None,
    ):
        """Initialize comparison lists for this rule.

        Local lists are loaded eagerly. Static HTTP(S) lists are loaded eagerly and
        registered for refresh and cleanup callbacks. Dynamic HTTP(S) templates that
        require event fields are loaded lazily during processing.

        Raises
        ------
        InvalidConfigurationError
            If neither the rule nor the processor provides ``list_search_base_path``.
        """
        list_search_base_path = self._get_list_search_base_path(list_search_base_path)
        self._callback_tag = callback_tag

        if not list_search_base_path.startswith("http"):
            self._init_list_comparison_from_local_file(list_search_base_path)
        else:
            base_template = Template(list_search_base_path)
            all_dynamic_identifiers: set[str] = set()

            for name, list_path in self._config.named_paths.items():
                full_path = base_template.safe_substitute(LOGPREP_LIST=list_path)
                full_path_with_env = Template(full_path).safe_substitute(ENV_VARS)

                dynamic_template = DottedTemplate(full_path_with_env)
                dynamic_identifiers = dynamic_template.get_identifiers()

                if dynamic_identifiers:
                    self._add_dynamic_compare_set(name=name, uri_template=dynamic_template)
                    all_dynamic_identifiers = all_dynamic_identifiers.union(dynamic_identifiers)
                else:
                    self._add_static_compare_set(name=name, path=full_path_with_env)

            self._all_dynamic_identifiers = tuple(all_dynamic_identifiers)

    def _add_static_compare_set(self, name: ListName, path: str):
        compare_set = _StaticCompareSet(name=name, content=set())
        self._static_sets.append(compare_set)
        self._load_and_refresh_uri(compare_set, path)

    def _add_dynamic_compare_set(self, name: ListName, uri_template: DottedTemplate):
        compare_set = _DynamicCompareSet(name=name, uri_template=uri_template)
        self._dynamic_sets.append(compare_set)

    def _update_compare_sets_via_http(self, getter: Getter, compare_set: _CompareSet):
        try:
            content = getter.get_list(content_field=self._config.content_field)
            file_elements = set(elem for elem in content if not elem.startswith("#"))
            compare_set.update_content(getter.target, file_elements)
        except Exception as ex:
            if isinstance(compare_set, _StaticCompareSet):
                self._mark_failed(compare_set, error=ex)
            raise ex
        else:
            # TODO ugly check in hot path, better idea?
            if isinstance(compare_set, _StaticCompareSet):
                self._clear_failed(compare_set)

    def _recompute_failure_state(self):
        errors = [cs.error for cs in self._static_sets if cs.error]
        if errors:
            self.mark_failed(ExceptionGroup("rule failed due to list data retrieval", errors))
        else:
            self.clear_failed()

    def _mark_failed(self, compare_set: _StaticCompareSet, error: Exception):
        compare_set.error = error
        self._recompute_failure_state()

    def _clear_failed(self, compare_set: _StaticCompareSet):
        if compare_set.error:
            compare_set.error = None
            self._recompute_failure_state()

    def _init_list_comparison_from_local_file(self, list_search_base_path: str) -> None:
        content_field = self._config.content_field
        absolute_list_paths = [
            list_path for list_path in self._config.list_file_paths if list_path.startswith("/")
        ]
        if not list_search_base_path.endswith("/"):
            list_search_base_path = list_search_base_path + "/"
        converted_absolute_list_paths = [
            list_search_base_path + list_path
            for list_path in self._config.list_file_paths
            if not list_path.startswith("/")
        ]
        list_paths = [*absolute_list_paths, *converted_absolute_list_paths]
        for list_path in list_paths:
            compare_elements = GetterFactory.from_string(list_path).get_list(
                content_field=content_field
            )
            file_elements = (elem for elem in compare_elements if not elem.startswith("#"))
            filename = os.path.basename(list_path)
            self._static_sets.append(_StaticCompareSet(name=filename, content=set(file_elements)))

    def _load_and_refresh_uri(self, compare_set: _CompareSet, uri: str):
        getter = GetterFactory.from_string(uri)
        if not isinstance(getter, RefreshableGetter):
            raise TypeError(f"The target {uri} must be a url")

        update_func = functools.partial(
            self._update_compare_sets_via_http, getter=getter, compare_set=compare_set
        )

        update_func()
        tag = self._callback_tag
        key = (tag, uri, id(self))

        getter.add_callback(tag, update_func, deduplication_key=key)

        if isinstance(compare_set, _DynamicCompareSet):
            # only keep_alive dynamic entries, such that static entries live forever
            getter.keep_alive()
            cleanup_func = functools.partial(self._cleanup, compare_set=compare_set, uri=uri)
            getter.add_cleanup_callback(tag, cleanup_func, deduplication_key=key)

    def _cleanup(self, compare_set: _DynamicCompareSet, uri: str):
        compare_set.remove_content(uri)
        logger.debug("Deleted compare set for %s after cleanup", uri)

    def iter_compare_sets(self, event: dict) -> Generator[tuple[str, set]]:
        """Return the compare sets relevant for the current event.

        For local and static lists, this returns the already initialized compare sets.
        For dynamic HTTP(S) templates, event fields are used to resolve the target URL
        and missing compare sets are loaded lazily.

        Raises
        ------
        ValueError
            If a required event field is missing or is not a scalar value.
        Exception
            Re-raises the stored data loading error if a dynamic HTTP(S) list cannot be
            loaded, so the processor can apply the rule's failure tags.
        """

        if self._all_dynamic_identifiers:
            dynamic_values = {
                identifier: get_dotted_field_value(event, identifier)
                for identifier in self._all_dynamic_identifiers
            }

            for identifier, val in dynamic_values.items():
                if val is None:
                    raise ValueError(
                        f"missing event field {identifier!r} for dynamic list comparison path"
                    )
                if not isinstance(val, (str, int)):
                    raise ValueError(
                        f"value for list comparison field {identifier!r} is not a scalar value"
                    )

        for static_compare_set in self._static_sets:
            if static_compare_set.content is None or static_compare_set.error is not None:
                raise ValueError("invariant broken; rule should be in failed state")
            yield static_compare_set.name, static_compare_set.content

        for dynamic_compare_set in self._dynamic_sets:
            assert dynamic_values
            uri = dynamic_compare_set.uri_template.substitute(dynamic_values)
            content = dynamic_compare_set.uri_to_content.get(uri)
            if content is None:
                self._load_and_refresh_uri(dynamic_compare_set, uri)
            else:
                RefreshableGetter.keep_alive_for_target(uri)
            yield dynamic_compare_set.name, dynamic_compare_set.uri_to_content[uri]

    @property
    def failure_tags(self) -> list[str]:
        """Returns the failure tags"""
        return self._config.tag_on_failure
