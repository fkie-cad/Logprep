"""Abstract base class module for rule loaders."""

from abc import ABC, abstractmethod
from typing import Any, List, Type

from logprep.processor.base.rule import Rule


class RuleLoader(ABC):
    """Abstract base class for rule loaders."""

    source: Any

    rule_class: Type = Rule

    @property
    @abstractmethod
    def rules(self) -> List[Rule]:
        """Return a list of rules."""
