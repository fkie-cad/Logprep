"""This module is used to get documents that match a clusterer filter."""

from typing import Pattern
import re
from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class ClustererRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Clusterer"""

        target: str = field(validator=validators.instance_of(str))
        pattern: re.Pattern = field(
            validator=validators.instance_of(re.Pattern), converter=re.compile
        )
        repl: str = field(validator=validators.instance_of(str))

    # pylint: disable=C0111
    @property
    def target(self) -> str:
        return self._config.target

    @property
    def pattern(self) -> Pattern:
        return self._config.pattern

    @property
    def repl(self) -> str:
        return self._config.repl

    # pylint: enable=C0111
