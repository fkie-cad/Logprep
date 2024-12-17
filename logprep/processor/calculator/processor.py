"""
Calculator
==========

The Calculator can be used to calculate with or without field values.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - calculatorname:
        type: calculator
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.calculator.processor.Calculator.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.calculator.rule
"""

import re
from functools import cached_property

from pyparsing import ParseException

from logprep.processor.calculator.fourFn import BNF
from logprep.processor.calculator.rule import CalculatorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.decorators import timeout
from logprep.util.helper import get_source_fields_dict


class Calculator(FieldManager):
    """A Processor to calculate with and without field values"""

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        source_field_dict = get_source_fields_dict(event, rule)
        if self._handle_missing_fields(event, rule, rule.source_fields, source_field_dict.values()):
            return
        if self._has_missing_values(event, rule, source_field_dict):
            return

        expression = self._template(rule.calc, source_field_dict)
        try:
            result = self._calculate(event, rule, expression)
            if result is not None:
                self._write_target_field(event, rule, result)
        except TimeoutError as error:
            self._handle_warning_error(event, rule, error)

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
                return self.bnf.evaluate_stack()
            except ParseException as error:
                error.msg = f"({self.name}): expression '{error.line}' could not be parsed"
                self._handle_warning_error(event, rule, error)
            except ArithmeticError as error:
                error.args = [
                    f"({self.name}): expression '{rule.calc}' => '{expression}' results in "
                    + f"{error.args[0]}"
                ]
                self._handle_warning_error(event, rule, error)
            return None

        return calculate(event, rule, expression)
