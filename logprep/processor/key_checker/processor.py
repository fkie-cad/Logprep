import imp
from logprep.abc import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.key_checker.rule import KeyCheckerRule


class KeyChecker(Processor):
    rule_class: Rule = KeyCheckerRule

    def _apply_rules(self, event, rule):
        return super()._apply_rules(event, rule)
