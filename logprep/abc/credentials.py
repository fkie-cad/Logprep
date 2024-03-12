from abc import ABC, abstractmethod

from attrs import define, field, validators
from requests import Session


@define(kw_only=True)
class Credentials(ABC):

    _session: Session = field(validator=validators.instance_of((Session, type(None))), default=None)

    @abstractmethod
    def get_session(self):
        """Return a session with the credentials applied"""
        if self._session is None:
            self._session = Session()
        return self._session
