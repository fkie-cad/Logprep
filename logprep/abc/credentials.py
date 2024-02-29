from abc import ABC, abstractmethod

from attrs import define


@define(kw_only=True)
class Credentials(ABC):

    @abstractmethod
    def authenticate(self):
        pass
