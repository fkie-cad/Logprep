"""
Delete
-------

The `delete` is a processor that removes an entire event from further pipeline processing.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - deletename:
        type: delete
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""

from logprep.abc import Processor
from logprep.processor.delete.rule import DeleteRule


class Delete(Processor):
    """A processor that deletes processed log events from further pipeline process"""

    rule_class = DeleteRule

    def _apply_rules(self, event, rule):
        event.clear()
