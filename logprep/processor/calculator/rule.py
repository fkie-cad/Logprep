"""
Calculator
==========
"""
from functools import partial
import re
from attrs import field, define, validators
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.validators import min_len_validator

FIELD_PATTERN = r"\$\{([+&?]?[^\ ${]*)\}"


class CalculatorRule(FieldManagerRule):
    """CalculatorRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for Calculator"""

        calc: str = field(
            validator=[validators.instance_of(str), partial(min_len_validator, min_length=3)],
        )
        source_fields: list = field(factory=list)

        def __attrs_post_init__(self):
            self.source_fields = re.findall(FIELD_PATTERN, self.calc)

    @property
    def calc(self):
        """Returns the calculation expression"""
        return self._config.calc
