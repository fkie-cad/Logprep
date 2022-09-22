from logprep.abc import Processor
from logprep.processor.dissecter.rule import DissecterRule


class Dissecter(Processor):

    rule_class = DissecterRule

    def _apply_rules(self, event, rule):
        return super()._apply_rules(event, rule)
