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

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.dissector.processor import Dissector
from logprep.processor.grokker.rule import GrokkerRule
from logprep.util.helper import add_field_to, get_dotted_field_value


class Grokker(Dissector):
    """A processor that ..."""

    rule_class = GrokkerRule

    @define(kw_only=True)
    class Config(Dissector.Config):
        """Config of Grokker"""

        custom_patterns_dir: str = field(default="", validator=validators.instance_of(str))
        """(Optional) A list of dirs to load patterns from. All files in all dirs will be loaded
        recursively. 
        """

    def _apply_rules(self, event: dict, rule: GrokkerRule):
        conflicting_fields = []
        for dotted_field, grok in rule.actions.items():
            field_value = get_dotted_field_value(event, dotted_field)
            result = grok.match(field_value)
            if result is None:
                continue
            for dundered_fields, value in result.items():
                if value is None:
                    continue
                dotted_field = grok.field_mapper.get(dundered_fields)
                success = add_field_to(
                    event, dotted_field, value, rule.extend_target_list, rule.overwrite_target
                )
                if not success:
                    conflicting_fields.append(dotted_field)
        if conflicting_fields:
            raise FieldExistsWarning(self, rule, event, conflicting_fields)

    def setup(self):
        super().setup()
        if self._config.custom_patterns_dir:
            for rule in self.rules:
                rule.set_mapping_actions(self._config.custom_patterns_dir)
