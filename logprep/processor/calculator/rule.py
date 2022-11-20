from attrs import field, define, validators, fields
from logprep.processor.field_manager.rule import FieldManagerRule


class CalculatorRule(FieldManagerRule):
    @define(kw_only=True)
    class Config(FieldManagerRule.Config):

        calc: str = field(validator=validators.instance_of(str))
        source_fields: list = field(factory=list)
