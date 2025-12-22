"""
ListComparison
==============

The `list_comparison` processor allows to compare values of source fields against lists provided
as files.


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

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.helper import add_fields_to, get_dotted_field_value


class ListComparison(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """ListComparison config"""

        list_search_base_path: str = field(validator=validators.instance_of(str))
        """Relative list paths in rules will be relative to this path if this is set.
        This parameter is optional. For string format see :ref:`getters`.
        You can also pass a template with keys from environment,
        e.g.,  :code:`${<your environment variable>}`. The special key :code:`${LOGPREP_LIST}`
        will be filled by this processor. """

    rule_class = ListComparisonRule

    def setup(self):
        super().setup()
        for rule in self.rules:
            rule.init_list_comparison(self._config.list_search_base_path)

    def _apply_rules(self, event, rule):
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
            fields = {f"{rule.target_field}.{comparison_key}": comparison_result}
            add_fields_to(event, fields, rule=rule, merge_with_target=True)

    def _list_comparison(self, rule: ListComparisonRule, event: dict) -> tuple[list, str]:
        """Check if field value violates block or allow list.

        Returns
        -------
        tuple[list[str], str]
            The result of the comparison, as well as a dictionary containing the result and a list
            of filenames pertaining to said result.

        """

        field_value_to_be_checked = get_dotted_field_value(event, rule.source_fields[0])
        value_list = (
            field_value_to_be_checked
            if isinstance(field_value_to_be_checked, list)
            else [field_value_to_be_checked]
        )

        list_matches = self._get_lists_matching_with_values(rule, value_list, event)

        if len(list_matches) == 0:
            return list(rule.compare_sets.keys()), "not_in_list"
        return list_matches, "in_list"

    def _get_lists_matching_with_values(
        self, rule: ListComparisonRule, value_list: list, _: dict
    ) -> list:
        """Iterate over string lists, check if element is in any."""
        list_matches = []
        for value in value_list:
            for compare_list in rule.compare_sets:
                if compare_list in list_matches:
                    continue
                if value in rule.compare_sets[compare_list]:
                    list_matches.append(compare_list)
        return list_matches
