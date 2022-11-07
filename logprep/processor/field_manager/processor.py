from functools import partial
from itertools import chain
from logprep.abc import Processor
from logprep.processor.base.rule import SourceTargetRule
from logprep.util.helper import (
    get_dotted_field_value,
    add_field_to,
    add_and_overwrite,
    append_as_list,
)


class FieldManager(Processor):

    rule_class = SourceTargetRule

    def _apply_rules(self, event, rule):
        field_values = [
            get_dotted_field_value(event, source_field) for source_field in rule.source_fields
        ]
        if len(field_values) == 1 and not rule.extend_target_list:
            field_values = field_values.pop()
        if rule.extend_target_list and rule.overwrite_target:
            field_values_lists = list(filter(lambda x: isinstance(x, list), field_values))
            field_values_not_list = list(
                chain(filter(lambda x: not isinstance(x, list), field_values))
            )
            target_field_value = sorted(
                list(
                    {
                        *list(chain(*field_values_lists)),
                        *field_values_not_list,
                    }
                )
            )
            add_and_overwrite(event, rule.target_field, target_field_value)
        if rule.extend_target_list and not rule.overwrite_target:
            target_field_value = get_dotted_field_value(event, rule.target_field)
            field_values_lists = list(filter(lambda x: isinstance(x, list), field_values))
            field_values_not_list = list(
                chain(filter(lambda x: not isinstance(x, list), field_values))
            )
            if isinstance(target_field_value, list):
                target_field_value = sorted(
                    list(
                        {
                            *target_field_value,
                            *list(chain(*field_values_lists)),
                            *field_values_not_list,
                        }
                    )
                )
            else:
                target_field_value = field_values
            add_and_overwrite(event, rule.target_field, target_field_value)
        if not rule.extend_target_list and not rule.overwrite_target:
            add_field_to(
                event,
                rule.target_field,
                field_values,
                extends_lists=rule.extend_target_list,
                overwrite_output_field=rule.overwrite_target,
            )
        if not rule.extend_target_list and rule.overwrite_target:
            add_and_overwrite(event, rule.target_field, field_values)
