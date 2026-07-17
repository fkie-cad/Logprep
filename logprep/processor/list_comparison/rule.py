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

import logging
import os.path

from attrs import define, field, validators

from logprep.factory_error import InvalidConfigurationError
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.dotted_template import DottedTemplate
from logprep.util.getter import (
    GetterFactory,
    HttpGetter,
    RefreshableGetter,
)
from logprep.util.helper import get_dotted_field_value

logger = logging.getLogger()


class ListComparisonRule(FieldManagerRule):
    """Check if documents match a filter."""

    _compare_sets: dict[str, set]

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for ListComparisonRule"""

        list_file_paths: list[str] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str))
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

    def __init__(
        self,
        filter_rule: FilterExpression,
        config: "ListComparisonRule.Config",
        processor_name: str,
    ):
        super().__init__(filter_rule, config, processor_name)
        self._config: ListComparisonRule.Config = self._config
        self._compare_sets = {}
        self._callback_tag = ""
        self._is_dynamic_http = False
        self._dynamic_templates: tuple[DottedTemplate, ...] = ()
        self._dynamic_identifiers: tuple[str, ...] = ()

    def _get_list_search_base_path(self, list_search_base_path: str | None) -> str:
        if self._config.list_search_base_path:
            return self._config.list_search_base_path
        elif list_search_base_path:
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
            self._config.list_search_base_path = (
                list_search_base_path
                if not self._config.list_search_base_path
                else self._config.list_search_base_path
            )

            base_template = DottedTemplate(self._config.list_search_base_path)

            # Check if this is a static (eagerly loaded) or dynamic (lazily loaded) list_comparison
            if any(
                identifier not in [*os.environ, "LOGPREP_LIST"]
                for identifier in base_template.get_identifiers()
            ):
                self._is_dynamic_http = True
                self._dynamic_templates = tuple(
                    DottedTemplate(
                        base_template.safe_substitute({**os.environ, "LOGPREP_LIST": list_path})
                    )
                    for list_path in self._config.list_file_paths
                )
                self._dynamic_identifiers = tuple(
                    dict.fromkeys(
                        identifier
                        for template in self._dynamic_templates
                        for identifier in template.get_identifiers()
                    )
                )
                return

            self._init_static_http_list_comparison()

    def _update_compare_sets_via_http(
        self, http_getter: HttpGetter, fully_resolved_uri: str, *, mark_rule_failed: bool = True
    ) -> set[dict] | None:
        try:
            content = http_getter.get_list(content_field=self._config.content_field)
            file_elements = (elem for elem in content if not elem.startswith("#"))
            self._compare_sets[fully_resolved_uri] = set(file_elements)
        except Exception as ex:
            if mark_rule_failed:
                self.mark_failed(error=ex)
                return None
            else:
                raise ex
        else:
            self.clear_failed()
            return self._compare_sets[fully_resolved_uri]

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
            self._compare_sets.update({filename: set(file_elements)})

    def _init_static_http_list_comparison(self) -> None:
        assert self._config.list_search_base_path

        for list_path in self._config.list_file_paths:
            resolved = DottedTemplate(self._config.list_search_base_path).substitute(
                {**os.environ, **{"LOGPREP_LIST": list_path}}
            )
            self._load_http_compare_set(resolved)

    def _load_http_compare_set(
        self, resolved_uri: str, *, dynamic: bool = False
    ) -> set[dict] | None:
        http_getter = GetterFactory.from_string(resolved_uri)
        if not isinstance(http_getter, HttpGetter):
            raise TypeError(f"The target {resolved_uri} must be a url")

        http_getter.keep_alive()

        compare_set = self._update_compare_sets_via_http(
            http_getter, resolved_uri, mark_rule_failed=not dynamic
        )
        tag = self._callback_tag

        http_getter.add_callback(
            tag,
            self._update_compare_sets_via_http,
            deduplication_key=(tag, resolved_uri, id(self)),
            fnc_args=[
                http_getter,
                resolved_uri,
            ],
            fnc_kwargs={"mark_rule_failed": not dynamic},
        )

        http_getter.add_cleanup_callback(
            tag,
            self._cleanup,
            deduplication_key=(tag, resolved_uri, id(self)),
            fnc_args=[resolved_uri],
        )
        return compare_set

    def _cleanup(self, resolved_uri: str):
        self._compare_sets.pop(resolved_uri, None)
        logger.debug("Deleted compare set for %s after cleanup", resolved_uri)

    def get_dynamic_set(self, event: dict) -> dict[str, set]:
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
        if not self._is_dynamic_http:
            return self._compare_sets

        compare_sets_result: dict[str, set] = {}
        assert self._config.list_search_base_path

        if not self._config.list_search_base_path.startswith("http"):
            return self._compare_sets

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

        for tmpl in self._dynamic_templates:
            dynamic_resolved = tmpl.substitute(key_val)

            if dynamic_resolved in self._compare_sets:
                RefreshableGetter.keep_alive_for_target(dynamic_resolved)

                compare_sets_result[dynamic_resolved] = self._compare_sets[dynamic_resolved]
                continue

            compare_set = self._load_http_compare_set(dynamic_resolved, dynamic=True)
            assert compare_set is not None

            compare_sets_result[dynamic_resolved] = compare_set

        return compare_sets_result

    @property
    def compare_sets(self) -> dict[str, set]:
        """Returns the comparison sets"""
        return self._compare_sets

    @property
    def failure_tags(self) -> list[str]:
        """Returns the failure tags"""
        return self._config.tag_on_failure
