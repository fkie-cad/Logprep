# pylint: disable=missing-docstring
# pylint: disable=abstract-method
from logprep.processor.base.rule import Rule
from logprep.processor.base.processor import RuleBasedProcessor


class TestProcessor(RuleBasedProcessor):
    def _apply_rules(self, event: dict, rule: Rule):
        pass
