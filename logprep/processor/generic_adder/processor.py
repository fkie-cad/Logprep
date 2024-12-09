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
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.generic_adder.processor.GenericAdder.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.generic_adder.rule
"""

from logprep.abc.processor import Processor
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.util.helper import add_fields_to


class GenericAdder(Processor):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = GenericAdderRule

    def _apply_rules(self, event: dict, rule: GenericAdderRule):
        items_to_add = rule.add
        if items_to_add:
            add_fields_to(event, items_to_add, rule, rule.extend_target_list, rule.overwrite_target)
