from logprep.abc import Processor
from .rule import CalculatorRule


class Calculator(Processor):

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        pass
