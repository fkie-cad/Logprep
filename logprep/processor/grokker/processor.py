"""
Grokker
============

The `grokker` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: grokker
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from attrs import define, field, validators

from logprep.processor.dissector.processor import Dissector
from logprep.processor.grokker.rule import GrokkerRule


class Grokker(Dissector):
    """A processor that ..."""

    rule_class = GrokkerRule

    @define(kw_only=True)
    class Config(Dissector.Config):
        """ Config of ..."""
        ...

    def _apply_rules(self, event, rule):
        pass