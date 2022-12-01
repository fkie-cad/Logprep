"""
Requester
============
"""
from typing import List, Tuple, Any

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite


class Requester(Processor):
    """A processor that copies, moves or merges source fields to one target field"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        pass
