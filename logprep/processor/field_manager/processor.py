from logprep.abc import Processor
from logprep.processor.base.rule import SourceTargetRule
from logprep.util.helper import get_dotted_field_value, add_field_to


class FieldManager(Processor):

    rule_class = SourceTargetRule

    def _apply_rules(self, event, rule):
        field_value = get_dotted_field_value(event, rule.source_fields[0])
        add_field_to(
            event, rule.target_field, field_value, overwrite_output_field=rule.overwrite_target
        )
