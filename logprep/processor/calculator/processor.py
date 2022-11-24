"""
Calculator
==========

The Calculator can be used to calculate with or without field values.
For further information for the rule language see: :ref:`calulator_rule`

"""
from functools import partial
import re

from pyparsing import ParseException

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.util.helper import add_field_to, get_dotted_field_value

from .fourFn import BNF, evaluate_stack, exprStack
from .rule import CalculatorRule


class Calculator(Processor):
    """A Processor to calculate with and without field values"""

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        source_fields = rule.source_fields
        source_field_values = map(partial(get_dotted_field_value, event), source_fields)
        source_field_dict = dict(zip(source_fields, source_field_values))
        self._check_for_missing_values(event, rule, source_field_dict)
        expression = self._template(rule.calc, source_field_dict)
        result = self._calculate(event, rule, expression)
        self._write_target_field(event, rule, result)

    @staticmethod
    def _template(string: str, source: dict) -> str:
        for key, value in source.items():
            key = key.replace(".", r"\.")
            pattern = r"\$\{(" + rf"{key}" + r")\}"
            string = re.sub(pattern, str(value), string)
        return string

    def _calculate(self, event, rule, expression):
        try:
            _ = BNF().parseString(expression, parseAll=True)
            result = evaluate_stack(exprStack[:])
        except ParseException as error:
            error.msg = f"({self.name}): expression '{error.line}' could not be parsed"
            self._handle_warning_error(event, rule, error)
        except ArithmeticError as error:
            error.args = [
                (
                    f"({self.name}): expression '{rule.calc}'"
                    f" => '{expression}' results in {error.args[0]}"
                )
            ]
            self._handle_warning_error(event, rule, error)
        return result

    def _write_target_field(self, event, rule, result):
        add_successful = add_field_to(
            event,
            output_field=rule.target_field,
            content=result,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
        if not add_successful:
            error = DuplicationError(self.name, [rule.target_field])
            self._handle_warning_error(event, rule, error)

    def _check_for_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(lambda x: x[1] in [None, ""], source_field_dict.items())).keys()
        )
        if missing_fields:
            error = BaseException(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)
