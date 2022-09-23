"""
Dissecter
---------

The `dissecter` is a processor that tokenizes incoming strings using defined patterns.
The behavior is based of the logstash dissect filter plugin.

For further information see: https://www.elastic.co/guide/en/logstash/current/plugins-filters-dissect.html


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - dissectername:
        type: dissecter
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from logprep.abc import Processor
from logprep.processor.dissecter.rule import DissecterRule


class Dissecter(Processor):
    """A processor that tokenizes field values to new fields and converts datatypes"""

    rule_class = DissecterRule

    def _apply_rules(self, event, rule):
        pass
