"""module for getter interface"""
from abc import ABC, abstractmethod

from attrs import define, field, validators


@define(kw_only=True)
class Getter(ABC):
    """abstract base class describing the getter interface and providing of factory method"""

    protocol: str = field(validator=validators.instance_of(str))
    target: str = field(validator=validators.instance_of(str))

    @abstractmethod
    def get(self) -> str:
        """get the content

        Returns
        -------
        str
            the unparsed content
        """
