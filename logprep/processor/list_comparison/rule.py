"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

Processor-specific rule configuration is done using the mandatory field :code:`list_comparison`.

The fields :code:`source_fields` and :code:`target_field` are used to define which field value
flows into the comparison and where the results flow to, respectively.
The processor is able to handle multiple lists and checks if the values referenced by
:code:`source_fields` have any intersection.

The lists used for the comparison are specified using a combination of :code:`list_search_base_path`
and :code:`list_paths` or :code:`list_file_paths`.
:code:`list_search_base_path` can be specified on the processor- and/or the rule-level, whereas the
rule-level takes precedence if both are set.

The actual list URIs to collect data from are derived in different ways for files and HTTP(s) paths:

For **file paths**, absolute paths in :code:`list_paths` or :code:`list_file_paths` are kept as-is.
Relative paths are transformed to absolute paths by using :code:`list_search_base_path` as a prefix.
A forward-slash is appended to :code:`list_search_base_path` before joining (if it has none).
The identifying name for each list is either taken from the key of :code:`list_paths` (if specified)
or it is derived from the basename of each path.

For **HTTP(s) paths**, :code:`list_search_base_path` has to carry a `${LOGPREP_LIST}` placeholder
which is used to inject the sub-paths from :code:`list_paths` or :code:`list_file_paths` literally.
Also, environment variables are interpolated in the process, for instance if the data source for the
lists is an API, for which domain/host/port etc. are supplied via the environment.
Additionally, field values can be injected into the paths using the same notation and
(potentially dotted) field references.
A URI with field references is considered *dynamic* and has considerable performance implications,
as every new concrete path needs to be fetched ad-hoc during event processing.
Caching and cache timeouts are used to balance performance and memory demands.

Results of the list comparison are written to :code:`target_field`.
If there was any intersection between :code:`source_fields` and any list, a sub-field called
`"in_list"` is populated, which in turn holds a list of all matching list names.
If there was no intersection, `"not_in_list"` is populated instead with all list names which
were tested in the comparison.
Do note that only one of these responses is present at a time.

In the following example, the field :code:`user_agent` will be checked against the provided list
(:code:`/lists/users/privileged.txt`).
Assuming that the value :code:`non_privileged_user` will match the provided list,
the result of the list comparison (:code:`in_list`) will be added to the
target field :code:`compare_result`.

..  code-block:: yaml
    :linenos:
    :caption: Example rule to compare a field against a provided file list.

    filter: 'user_agent'
    list_comparison:
        source_fields: ['user_agent']
        target_field: 'compare_result'
        list_file_paths:
            - users/privileged.txt
        list_search_base_path: /lists

..  code-block:: yaml
    :linenos:
    :caption: Example rule to compare a field against remotely served lists.

    filter: 'user_agent'
    list_comparison:
        source_fields: ['user.id']
        target_field: 'user.classification'
        list_paths:
            BLOCKLIST: users/blocked
            PRIVILEGED: users/privileged
        list_search_base_path: https://${LOGPREP_LIST_HOST}/api/${LOGPREP_LIST}

.. note::

    Currently, it is not possible to check in more than one :code:`source_field` per rule.

.. autoclass:: logprep.processor.list_comparison.rule.ListComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for list_comparison:
-----------------------------

.. datatemplate:import-module:: tests.unit.processor.list_comparison.test_list_comparison
   :template: testcase-renderer.tmpl

"""

import functools
import logging
import os.path
from abc import ABC, abstractmethod
from collections.abc import Generator, Sequence
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


@define(kw_only=True)
class _CompareSet(ABC):
    name: ListName

    @abstractmethod
    def update_content(self, uri: str, content: ListContent | None) -> None:
        """Updates the cached and post-processed content"""


@define(kw_only=True)
class _StaticCompareSet(_CompareSet):
    content: ListContent | None
    error: Exception | None = field(default=None)

    def update_content(self, _, content: ListContent | None) -> None:
        self.content = content


@define(kw_only=True)
class _DynamicCompareSet(_CompareSet):
    uri_template: DottedTemplate
    uri_to_content: dict[str, ListContent] = field(factory=dict)

    def update_content(self, uri: str, content: ListContent | None) -> None:
        if content is None:
            self.remove_content(uri)
        else:
            self.uri_to_content[uri] = content

    def remove_content(self, uri: str) -> None:
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
        Values represent the paths used to populate `${LOGPREP_LIST}`.

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
        mapping: dict = field(factory=dict, init=False, repr=False, eq=False)
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

        def __attrs_post_init__(self) -> None:
            if self.list_file_paths and self.list_paths:
                raise ValueError("`list_file_paths` and `list_paths` must not both be specified")
            if not self.list_file_paths and not self.list_paths:
                raise ValueError("one of `list_file_paths` or `list_paths` needs to be specified")

    def __init__(
        self,
        filter_rule: FilterExpression,
        config: "ListComparisonRule.Config",
        processor_name: str,
    ):
        super().__init__(filter_rule, config, processor_name)
        self._config: ListComparisonRule.Config = self._config
        self._callback_tag = ""
        self._static_sets: list[_StaticCompareSet] = []
        self._dynamic_sets: list[_DynamicCompareSet] = []
        self._all_dynamic_identifiers: tuple[str, ...] = ()
        self.compare_set_names: Sequence[str] = []

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
        base_path: str | None = None,
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
        base_path = self._get_list_search_base_path(base_path)
        self._callback_tag = callback_tag

        list_paths = list(self._config.list_paths.values()) or self._config.list_file_paths
        list_names = list(self._config.list_paths.keys()) or None

        if not base_path.startswith("http"):
            self._init_list_comparison_from_local_file(base_path, list_paths, list_names)
        else:
            self._init_list_comparison_from_http(base_path, list_paths, list_names)

    def _add_static_compare_set(self, name: ListName, path: str) -> None:
        compare_set = _StaticCompareSet(name=name, content=set())
        self._static_sets.append(compare_set)
        self._load_and_refresh_uri(compare_set, path)

    def _add_dynamic_compare_set(self, name: ListName, uri_template: DottedTemplate) -> None:
        compare_set = _DynamicCompareSet(name=name, uri_template=uri_template)
        self._dynamic_sets.append(compare_set)

    def _update_compare_sets_via_http(self, getter: Getter, compare_set: _CompareSet) -> None:
        try:
            content = self._get_list_contents_from_getter(getter)
            compare_set.update_content(getter.target, content)
        except Exception as ex:
            if isinstance(compare_set, _StaticCompareSet):
                self._mark_failed(compare_set, error=ex)
                return
            raise
        else:
            # TODO ugly check in hot path, better idea?
            if isinstance(compare_set, _StaticCompareSet):
                self._clear_failed(compare_set)

    def _recompute_failure_state(self) -> None:
        errors = [cs.error for cs in self._static_sets if cs.error]
        if errors:
            if len(errors) == 1:
                self.mark_failed(errors[0])
            else:
                self.mark_failed(ExceptionGroup("rule failed due to list data retrieval", errors))
        else:
            self.clear_failed()

    def _mark_failed(self, compare_set: _StaticCompareSet, error: Exception) -> None:
        compare_set.error = error
        self._recompute_failure_state()

    def _clear_failed(self, compare_set: _StaticCompareSet) -> None:
        if compare_set.error:
            compare_set.error = None
            self._recompute_failure_state()

    def _init_list_comparison_from_local_file(
        self, base_path: str, list_paths: Sequence[str], list_names: Sequence[str] | None
    ):
        if not base_path.endswith("/"):
            base_path = base_path + "/"

        absolute_paths = [path if path.startswith("/") else base_path + path for path in list_paths]

        if list_names is None:
            list_names = [os.path.basename(path) for path in absolute_paths]
            if len(list_names) != len(set(list_names)):
                raise ValueError(
                    "list names need to be unique; the basename for these entries is not:"
                    f"{', '.join(absolute_paths)}"
                )

        for list_name, list_path in zip(list_names, absolute_paths):
            content = self._get_list_contents_from_getter(GetterFactory.from_string(list_path))
            self._static_sets.append(_StaticCompareSet(name=list_name, content=content))

        self.compare_set_names = list_names

    def _init_list_comparison_from_http(
        self, base_path: str, list_paths: Sequence[str], list_names: Sequence[str] | None
    ):
        base_template = DottedTemplate(base_path)

        if "LOGPREP_LIST" not in base_template.get_identifiers():
            raise ValueError(
                "LOGPREP_LIST needs to be configured in list_search_base_path,"
                f"it is not: {base_path}"
            )

        all_dynamic_identifiers: set[str] = set()

        if list_names is None:
            list_names = list_paths

        for name, list_path in zip(list_names, list_paths):
            full_path = base_template.safe_substitute(LOGPREP_LIST=list_path)
            # TODO maybe only allow uppercase and specially prefixed env vars like in EnvTemplate
            full_path_with_env = DottedTemplate(full_path).safe_substitute(ENV_VARS)

            dynamic_template = DottedTemplate(full_path_with_env)
            dynamic_identifiers = dynamic_template.get_identifiers()

            if dynamic_identifiers:
                self._add_dynamic_compare_set(name=name, uri_template=dynamic_template)
                all_dynamic_identifiers = all_dynamic_identifiers.union(dynamic_identifiers)
            else:
                self._add_static_compare_set(name=name, path=full_path_with_env)

        self._all_dynamic_identifiers = tuple(all_dynamic_identifiers)
        self.compare_set_names = list_names

    def _transform_and_filter_list_element(self, elem: str) -> str | None:
        return elem if not elem.startswith("#") else None

    def _get_list_contents_from_getter(self, getter: Getter) -> set:
        raw_list = getter.get_list(content_field=self._config.content_field)
        return {
            elem
            for elem in map(self._transform_and_filter_list_element, raw_list)
            if elem is not None
        }

    def _load_and_refresh_uri(self, compare_set: _CompareSet, uri: str) -> None:
        getter = GetterFactory.from_string(uri)
        if not isinstance(getter, RefreshableGetter):
            raise TypeError(f"The target {uri} must be a url")

        update_func = functools.partial(
            self._update_compare_sets_via_http, getter=getter, compare_set=compare_set
        )

        update_func()
        tag = self._callback_tag
        key = (uri, id(compare_set))

        getter.add_callback(tag, update_func, deduplication_key=key)

        if isinstance(compare_set, _DynamicCompareSet):
            # only keep_alive dynamic entries, such that static entries live forever
            getter.keep_alive()
            cleanup_func = functools.partial(self._cleanup, compare_set=compare_set, uri=uri)
            getter.add_cleanup_callback(tag, cleanup_func, deduplication_key=key)

    def _cleanup(self, compare_set: _DynamicCompareSet, uri: str) -> None:
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
