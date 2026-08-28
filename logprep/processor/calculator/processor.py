"""
|PROCESSOR_NAME|
================

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

from typing import TypeAlias

from logprep.processor.calculator.fourFn import (
    ASTNode,
    EvaluationError,
    InvalidSyntaxError,
    MissingValueError,
    compile_expression,
)
from logprep.processor.calculator.rule import CalculatorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.decorators import timeout

ExpressionCacheEntry: TypeAlias = ASTNode | Exception


class Calculator(FieldManager):
    """A Processor to calculate with and without field values"""

    rule_class = CalculatorRule

    _expression_cache: dict[str, ExpressionCacheEntry] = {}

    def __precompile(self, expression: str) -> ExpressionCacheEntry:
        if expression in self._expression_cache:
            return self._expression_cache[expression]

        try:
            self._expression_cache[expression] = compile_expression(expression)
        except InvalidSyntaxError as error:
            self._expression_cache[expression] = error

        return self._expression_cache[expression]

    def _apply_rules(self, event, rule):
        # TODO check all rules can be precompiled at init instead of
        # cached/lazy loading approach.
        cache_entry = self.__precompile(rule.calc)
        if isinstance(cache_entry, Exception):
            self._handle_warning_error(event, rule, cache_entry)
            return

        @timeout(seconds=rule.timeout)
        def calculate():
            return cache_entry.evaluate(event)

        try:
            result = calculate()
            if result is not None:
                self._write_target_field(event, rule, result)
        except MissingValueError as error:
            self._handle_missing_fields(
                event,
                rule,
                rule.source_fields,
                [None],  # TODO: interace for utility function is terrible.
            )
        except EvaluationError as error:
            self._handle_warning_error(event, rule, error)
        except TimeoutError as error:
            self._handle_warning_error(event, rule, error)
