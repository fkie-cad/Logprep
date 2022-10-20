from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.base.rule import Rule


class KeyCheckerRule(Rule):
    class Config:
        pass

    def __init__(self, filter_rule: FilterExpression, config: "KeyCheckerRule.Config"):
        """
        Instantiate ConcatenatorRule based on a given filter and processor configuration.

        Parameters
        ----------
        filter_rule : FilterExpression
            Given lucene filter expression as a representation of the rule's logic.
        config : "ConcatenatorRule.Config"
            Configuration fields from a given pipeline that refer to the processor instance.
        """
        super().__init__(filter_rule)
        self._config = config

    @staticmethod
    def _create_from_dict(rule: dict) -> "KeyCheckerRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("key_checker")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = KeyCheckerRule.Config(**config)
        return KeyCheckerRule(filter_expression, config)
