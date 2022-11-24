"""
Calculator
==========



"""
from functools import partial
from string import Template

from pyparsing import ParseException

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.util.helper import add_field_to, get_dotted_field_value

from .fourFn import BNF, evaluate_stack, exprStack
from .rule import CalculatorRule


class Calculator(Processor):
    """A Processor to calculate with field values"""

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        source_fields = rule.source_fields
        source_field_values = map(partial(get_dotted_field_value, event), source_fields)
        source_field_dict = dict(zip(source_fields, source_field_values))
        self._check_for_missing_values(event, rule, source_field_dict)
        template = Template(rule.calc)
        expression = template.substitute(source_field_dict)
        try:
            _ = BNF().parseString(expression, parseAll=True)
            result = evaluate_stack(exprStack[:])
        except ParseException as error:
            error.msg = f"({self.name}): expression '{error.line}' could not be parsed"
            self._handle_warning_error(event, rule, error)
        add_successful = add_field_to(event, output_field=rule.target_field, content=result)
        if not add_successful:
            error = DuplicationError(self.name, [rule.target_field])
            self._handle_warning_error(event, rule, error)

    def _check_for_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(self._filter_missing_or_empty, source_field_dict.items())).keys()
        )
        if missing_fields:
            error = BaseException(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)

    @staticmethod
    def _filter_missing_or_empty(item: tuple) -> bool:
        _, value = item
        if value is None:
            return True
        if value == "":
            return True
        return False
