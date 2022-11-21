"""
Calculator
==========



"""
from functools import partial
from string import Template
from logprep.abc import Processor
from logprep.util.helper import add_field_to, get_dotted_field_value
from .rule import CalculatorRule
from .fourFn import BNF, evaluate_stack, exprStack


class Calculator(Processor):
    """A Processor to calculate with field values"""

    rule_class = CalculatorRule

    def _apply_rules(self, event, rule):
        source_fields = rule.source_fields
        source_field_values = map(partial(get_dotted_field_value, event), source_fields)
        source_field_dict = dict(zip(source_fields, source_field_values))
        template = Template(rule.calc)
        expression = template.substitute(source_field_dict)
        _ = BNF().parseString(expression, parseAll=True)
        val = evaluate_stack(exprStack[:])
        add_field_to(event, output_field=rule.target_field, content=val)
