"""
StringSplitter
============

The `string_splitter` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: string_splitter
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from attrs import define, field, validators

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.string_splitter.rule import StringSplitterRule



class StringSplitter(FieldManager):
    """A processor that ..."""

    rule_class = StringSplitterRule

    @define(kw_only=True)
    class Config(FieldManager.Config):
        ...

    def _apply_rules(self, event, rule):
        ...