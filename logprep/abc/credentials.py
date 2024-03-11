from abc import ABC, abstractmethod

from attrs import define, field, validators
from requests import Session


@define(kw_only=True)
class Credentials(ABC):

    @abstractmethod
    def get_session(self):
        return Session()
