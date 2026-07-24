"""
GenericAdder
============
The `generic_adder` is a processor that adds new fields and values to documents based on a list.
The list resides inside a rule and/or inside a file.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - genericaddername:
        type: generic_adder
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.generic_adder.processor.GenericAdder.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.generic_adder.rule
"""

import typing
from typing import Sequence

from logprep.abc.processor import Processor
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.util.getter import RefreshableGetter
from logprep.util.helper import add_fields_to


class GenericAdder(Processor):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = GenericAdderRule

    @property
    def _rules(self) -> Sequence[GenericAdderRule]:
        """Returns all rules"""
        return typing.cast(Sequence[GenericAdderRule], self.rules)

    def setup(self):
        super().setup()
        for rule in self._rules:
            rule.init_generic_adder(self._job_tag_for_cleanup)

    def _apply_rules(self, event: dict, rule: GenericAdderRule):
        items_to_add = rule.add(event)
        if items_to_add:
            add_fields_to(event, items_to_add, rule, rule.merge_with_target, rule.overwrite_target)

    def _shut_down(self) -> None:
        RefreshableGetter.remove_callbacks_for_tag(self._job_tag_for_cleanup)
        return super()._shut_down()
