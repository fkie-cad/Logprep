from logprep.abc import Processor
from logprep.processor.base.rule import SourceTargetRule


class FieldManager(Processor):

    rule_class = SourceTargetRule

    def _apply_rules(self, event, rule):
        pass
