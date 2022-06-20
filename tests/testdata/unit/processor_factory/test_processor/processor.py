# pylint: disable=missing-docstring
# pylint: disable=abstract-method
from logprep.abc import Processor
from logprep.processor.base.rule import Rule


class TestProcessor(Processor):
    def _apply_rules(self, event: dict, rule: Rule):
        pass
