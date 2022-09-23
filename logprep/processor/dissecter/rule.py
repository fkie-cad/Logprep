"""Dissecter Rule Module"""
from attrs import define, validators, field, Factory
from logprep.processor.base.rule import Rule
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError


DISSECT = r"(%\{[A-Za-z0-9+&].*\})"
SEPERATOR = r"((?!%\{.*\}).+)"


class DissecterRule(Rule):
    """dissecter rule"""

    @define(kw_only=True)
    class Config:
        """Config for Dissecter"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(rf"^({DISSECT}{SEPERATOR})+{DISSECT}$"),
                ),
            ],
            default=Factory(dict),
        )
        convert_datatype: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.in_(["float", "int", "string"]),
                ),
            ],
            default=Factory(dict),
        )
        tag_on_failure: list = field(
            validator=validators.instance_of(list), default=["_dissectfailure"]
        )

    _config: "DissecterRule.Config"

    def __init__(self, filter_rule: FilterExpression, config: "DissecterRule.Config"):
        super().__init__(filter_rule)
        self._config = config

    def __eq__(self, other: "Rule") -> bool:
        return False

    @staticmethod
    def _create_from_dict(rule: dict) -> "DissecterRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("dissecter")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = DissecterRule.Config(**config)
        return DissecterRule(filter_expression, config)
