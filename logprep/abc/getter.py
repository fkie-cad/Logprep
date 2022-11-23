"""Module for getter interface"""
from abc import ABC, abstractmethod

from attrs import define, field, validators


@define(kw_only=True)
class Getter(ABC):
    """Abstract base class describing the getter interface and providing of a factory method."""

    protocol: str = field(validator=validators.instance_of(str))
    """Indicates the protocol for the factory to chose a matching getter."""
    target: str = field(validator=validators.instance_of(str))
    """The target which holds the content to return by get method."""

    @abstractmethod
    def get(self) -> str:
        """Get the content.

        Returns
        -------
        str
            The raw serialized content.
        """
