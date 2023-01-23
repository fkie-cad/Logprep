"""
Calculator
==========

The Calculator can be used to calculate with or without field values.
For further information for the rule language see: :ref:`calculator_rule`

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - calculatorname:
        type: calculator
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

"""
import re
from functools import cached_property

from pyparsing import ParseException

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.calculator.fourFn import BNF
from logprep.processor.calculator.rule import CalculatorRule
from logprep.util.helper import add_field_to, get_source_fields_dict
from logprep.util.decorators import timeout


class Calculator(Processor):
    """A Processor to calculate with and without field values"""

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        source_field_dict = get_source_fields_dict(event, rule)
        self._check_for_missing_values(event, rule, source_field_dict)
        expression = self._template(rule.calc, source_field_dict)
        try:
            result = self._calculate(event, rule, expression)
        except TimeoutError as error:
            self._handle_warning_error(event, rule, error)
        self._write_target_field(event, rule, result)

    @cached_property
    def bnf(self) -> BNF:
        """Holds the Backus-Naur Form definition

        Returns
        -------
        Forward
            a pyparsing Forward object
        """
        return BNF()

    @staticmethod
    def _template(string: str, source: dict) -> str:
        for key, value in source.items():
            key = key.replace(".", r"\.")
            pattern = r"\$\{(" + rf"{key}" + r")\}"
            string = re.sub(pattern, str(value), string)
        return string

    def _calculate(self, event, rule, expression):
        @timeout(seconds=rule.timeout)
        def calculate(event, rule, expression):
            try:
                _ = self.bnf.parseString(expression, parseAll=True)
                result = self.bnf.evaluate_stack()
            except ParseException as error:
                error.msg = f"({self.name}): expression '{error.line}' could not be parsed"
                self._handle_warning_error(event, rule, error)
            except ArithmeticError as error:
                error.args = [
                    f"({self.name}): expression '{rule.calc}' => '{expression}' results in "
                    + f"{error.args[0]}"
                ]
                self._handle_warning_error(event, rule, error)
            return result

        return calculate(event, rule, expression)

    def _write_target_field(self, event, rule, result):
        add_successful = add_field_to(
            event,
            output_field=rule.target_field,
            content=result,
            extends_lists=rule.extend_target_list,
            overwrite_output_field=rule.overwrite_target,
        )
        if not add_successful:
            raise DuplicationError(self.name, [rule.target_field])
