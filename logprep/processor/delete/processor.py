"""This module contains a delete processor that can be used for testing purposes."""

from logprep.abc import Processor
from logprep.processor.delete.rule import DeleteRule


class Delete(Processor):
    """A processor that deletes processed log events from further pipeline process"""

    rule_class = DeleteRule

    def _apply_rules(self, event, rule):
        event.clear()
