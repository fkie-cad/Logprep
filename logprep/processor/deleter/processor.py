"""
Deleter
=======

The `deleter` is a processor that removes an entire event from further pipeline processing.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - deletename:
        type: deleter
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.deleter.processor.Deleter.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.deleter.rule
"""

from logprep.abc.processor import Processor
from logprep.processor.deleter.rule import DeleterRule


class Deleter(Processor):
    """A processor that deletes processed log events from further pipeline process"""

    rule_class = DeleterRule

    def _apply_rules(self, event, rule):
        if rule.delete_event:
            event.clear()
