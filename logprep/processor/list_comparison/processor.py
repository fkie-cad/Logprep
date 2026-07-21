"""
ListComparison
==============

The `list_comparison` processor compares values of source fields against
comparison lists loaded from local files or HTTP(S) targets. HTTP base paths may
be static or templated with environment variables and event fields for dynamic,
lazy list loading.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - listcomparisonname:
        type: list_comparison
        rules:
            - tests/testdata/rules/rules
        list_search_base_path: /path/to/list/dir

.. autoclass:: logprep.processor.list_comparison.processor.ListComparison.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.list_comparison.rule
"""

import typing
from collections.abc import Iterable

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.getter import RefreshableGetter
from logprep.util.helper import (
    FieldValue,
    add_fields_to,
    get_dotted_field_value,
    join_dotted_fields,
)


class ListComparison(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """ListComparison config"""

        list_search_base_path: str | None = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """
        Base path used to resolve relative ``list_file_paths`` from rules.
        This setting is optional on the processor if every rule defines its own
        ``list_search_base_path``. It is required either here or in the rule config.

        The value may use getter syntax and may contain ``string.Template`` placeholders.
        Environment variables and ``${LOGPREP_LIST}`` are resolved during setup. For
        HTTP(S) paths, placeholders that are not environment variables are resolved from
        the event during processing, enabling dynamic list paths.
        """

    rule_class = ListComparisonRule

    def setup(self):
        super().setup()
        for rule in self.rules:
            rule = typing.cast(ListComparisonRule, rule)
            config = typing.cast(ListComparison.Config, self._config)
            rule.init_list_comparison(
                self._job_tag_for_cleanup,
                config.list_search_base_path,
            )

    def _apply_rules(self, event: dict[str, FieldValue], rule: ListComparisonRule) -> None:
        """
        Apply matching rule to given log event.
        In the process of doing so, add the result of comparing
        the log with a given list to the specified subfield. This subfield will contain
        a list of list comparison results that might be based on multiple rules.

        Parameters
        ----------
        event : dict
            Log message being processed.
        rule :
            Currently applied list comparison rule.

        """
        comparison_result, comparison_key = self._list_comparison(rule, event)
        if comparison_result is not None:
            fields = {join_dotted_fields((rule.target_field, comparison_key)): comparison_result}
            add_fields_to(event, fields, rule=rule, merge_with_target=True)

    def _list_comparison(
        self, rule: ListComparisonRule, event: dict[str, FieldValue]
    ) -> tuple[list[str], str]:
        """Check if field value violates block or allow list.

        Returns
        -------
        tuple[list[str], str]
            A list of matching list identifiers and the result key ``"in_list"``, or all
            evaluated list identifiers and the result key ``"not_in_list"`` if no value
            matched.
        """

        field_value_to_be_checked = get_dotted_field_value(event, rule.source_fields[0])
        value_list = (
            field_value_to_be_checked
            if isinstance(field_value_to_be_checked, list)
            else [field_value_to_be_checked]
        )

        matching_keys, all_keys = self._get_lists_matching_with_values(rule, value_list, event)
        if len(matching_keys) == 0:
            return list(all_keys), "not_in_list"
        return matching_keys, "in_list"

    def _get_lists_matching_with_values(
        self, rule: ListComparisonRule, value_list: list[FieldValue], event: dict[str, FieldValue]
    ) -> tuple[list[str], Iterable[str]]:
        """Return matching comparison-list identifiers and the evaluated compare set names.

        Dynamic list loading errors are converted to ``ProcessingWarning`` so the rule's
        failure tags are applied instead of producing a normal ``not_in_list`` result.
        """

        event_values = set(value_list)

        try:

            matches = [
                set_name
                for set_name, set_values in rule.iter_compare_sets(event)
                if not event_values.isdisjoint(set_values)
            ]

        except Exception as error:
            raise ProcessingWarning(str(error), rule, event) from error

        return matches, rule.compare_set_names

    def _shut_down(self) -> None:
        RefreshableGetter.remove_callbacks_for_tag(self._job_tag_for_cleanup)
        return super()._shut_down()
