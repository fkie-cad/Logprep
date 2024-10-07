"""
Replacer
============

The `replacer` processor ...

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: replacer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

.. autoclass:: logprep.processor.replacer.processor.Replacer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.replacer.processor.Replacer.rule
"""

from attrs import define, field, validators

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.replacer.rule import ReplacerRule


class Replacer(FieldManager):
    """A processor that ..."""

    rule_class = ReplacerRule

    def _apply_rules(self, event: dict, rule: ReplacerRule):
        for source_field in rule.mapping:
            source_field_value = event.get(source_field)
            actions = rule.actions[source_field]
            pass
