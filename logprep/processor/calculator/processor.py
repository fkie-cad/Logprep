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

from typing import Sequence, cast

from logprep.processor.calculator.fourFn import (
    EvaluationError,
    MissingValueError,
)
from logprep.processor.calculator.rule import CalculatorRule
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.decorators import timeout


class Calculator(FieldManager):
    """A Processor to calculate with and without field values"""

    rule_class = CalculatorRule

    @property
    def rules(self) -> Sequence[CalculatorRule]:
        """Returns all rules as Calculator rule"""
        return cast(Sequence[CalculatorRule], super().rules)

    def setup(self):
        super().setup()
        print("SETUP")
        for rule in self.rules:
            rule.init_calculator()

    def _apply_rules(self, event, rule):
        assert isinstance(rule, CalculatorRule)

        @timeout(seconds=rule.timeout)
        def calculate():
            return rule.program.evaluate(event)

        try:
            print("CALCULATE")
            result = calculate()
            print("RESULT", result)
            if result is not None:
                self._write_target_field(event, rule, result)
        except MissingValueError:
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
