"""module for getter interface"""
from abc import ABC, abstractmethod

from attrs import define, field, validators


@define(kw_only=True)
class Getter(ABC):
    """abstract base class describing the getter interface and providing of factory method"""

    protocol: str = field(validator=validators.instance_of(str))
    """indicates the protocol for the factory to chose a matching getter"""
    target: str = field(validator=validators.instance_of(str))
    """the target which holds the content to return by get method"""

    @abstractmethod
    def get(self) -> str:
        """get the content

        Returns
        -------
        str
            the unparsed content
        """
