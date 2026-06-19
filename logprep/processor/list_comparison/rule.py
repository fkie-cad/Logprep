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

import os.path
import re
from string import Template

from attrs import define, field, validators

from logprep.abc.getter import Getter
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.getter import GetterFactory, HttpGetter
from logprep.util.helper import get_dotted_field_value


@define(frozen=True)
class DynamicCompareKey:
    base_uri: str
    values: tuple[str | int | float | bool, ...]

    # def __init__(self, base_uri: str, used_values: tuple[str | int | float | bool, ...]) -> None:
    #     self.base_uri = base_uri
    #     self.values = used_values
    #     pass

    def render(self) -> str:
        it = iter([str(val) for val in self.values if val is not None])
        return PATH_RE.sub(lambda _: next(it), self.base_uri)


class ListComparisonRule(FieldManagerRule):
    """Check if documents match a filter."""

    _compare_sets: dict[DynamicCompareKey, set]

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
        list_search_base_path: str = field(validator=validators.instance_of(str), factory=str)
        """Base Path from where to find relative files from :code:`list_file_paths`.
        You can also pass a template with keys from environment,
        e.g.,  :code:`${<your environment variable>}`. The special key :code:`${LOGPREP_LIST}`
        will be filled by this processor. """
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

    def _get_list_search_base_path(self, list_search_base_path: str | None) -> str:
        if list_search_base_path is None:
            return self._config.list_search_base_path
        if self._config.list_search_base_path > list_search_base_path:
            return self._config.list_search_base_path
        return list_search_base_path

    def init_list_comparison(self, list_search_base_path: str | None = None):
        """init method for list_comparison lists"""
        list_search_base_path = self._get_list_search_base_path(list_search_base_path)
        if not list_search_base_path.startswith("http"):
            self._init_list_comparison_from_local_file(list_search_base_path)

    def _update_compare_sets_via_http(
        self, http_getter: HttpGetter, dck: DynamicCompareKey
    ) -> set[dict] | None:
        try:
            content = http_getter.get_list(content_field=self._config.content_field)
            file_elements = (elem for elem in content if not elem.startswith("#"))
            self._compare_sets[dck] = set(file_elements)
        except Exception as ex:
            self.mark_failed(error=ex)
            return None
        else:
            self.clear_failed()
            return self._compare_sets[dck]

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
            dck = DynamicCompareKey(filename, ())
            self._compare_sets.update({dck: set(file_elements)})

    def get_dynamic_set(self, event: dict) -> dict[DynamicCompareKey, set]:
        compare_sets_result: dict[DynamicCompareKey, set] = {}

        # def replace_placeholder_with_dotted_field(match: re.Match) -> str:
        #     val = get_dotted_field_value(event, match.group(1))
        #     if not isinstance(val, (str, int, float, bool, type(None))):
        #         raise ValueError("This is not a valid scalar value")
        #     return str(val)

        for list_path in self._config.list_file_paths:
            list_search_base_path_resolved = Template(
                self._config.list_search_base_path
            ).substitute({**os.environ, **{"LOGPREP_LIST": list_path}})

            used_values = tuple(
                value
                for path in PATH_RE.findall(list_search_base_path_resolved)
                if isinstance(
                    value := get_dotted_field_value(event, path), (str | float | int | bool)
                )
            )
            dck = DynamicCompareKey(list_search_base_path_resolved, used_values)

            it = iter(dck.values)
            dynamic_resolved = PATH_RE.sub(lambda m: str(next(it)), dck.base_uri)

            if dck in self._compare_sets:
                HttpGetter.signal_called_for_target(dynamic_resolved)
                compare_sets_result[dck] = self._compare_sets[dck]
                continue

            http_getter = GetterFactory.from_string(dynamic_resolved)
            if not isinstance(http_getter, HttpGetter):
                raise TypeError(f"The target {dynamic_resolved} must be a url")

            http_getter.signal_called()

            compare_set = self._update_compare_sets_via_http(http_getter, dck)
            http_getter.add_callback(self._update_compare_sets_via_http, http_getter, dck)
            if compare_set:
                compare_sets_result.update({dck: compare_set})

        return compare_sets_result

    @property
    def compare_sets(self) -> dict[DynamicCompareKey, set]:  # pylint: disable=missing-docstring
        return self._compare_sets

    @property
    def failure_tags(self) -> list[str]:
        """Returns the failure tags"""
        return self._config.tag_on_failure


PATH_RE = re.compile(r"\$\{([^}]+)\}")
