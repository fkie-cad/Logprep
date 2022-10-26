"""
Deleter
-------

The `deleter` is a processor that removes an entire event from further pipeline processing.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - deletename:
        type: deleter
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from logprep.abc import Processor
from logprep.processor.deleter.rule import DeleterRule


class Deleter(Processor):
    """A processor that deletes processed log events from further pipeline process"""

    rule_class = DeleterRule

    def _apply_rules(self, event, rule):
        if rule.delete_event:
            event.clear()
