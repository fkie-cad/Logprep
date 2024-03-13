"""Abstract Base Class for Credentials"""

import logging
from abc import ABC, abstractmethod

from attrs import define, field, validators
from requests import HTTPError, Session


class CredentialsBadRequestError(Exception):
    """Raised when the API returns a 400 Bad Request error"""


@define(kw_only=True)
class Credentials(ABC):
    """Abstract Base Class for Credentials"""

    _logger = logging.getLogger(__name__)

    _session: Session = field(validator=validators.instance_of((Session, type(None))), default=None)

    @abstractmethod
    def get_session(self):
        """Return a session with the credentials applied"""
        if self._session is None:
            self._session = Session()
        return self._session

    def _no_authorization_header(self, session):
        return session.headers.get("Authorization") is None

    def _handle_bad_requests_errors(self, response):
        try:
            response.raise_for_status()
        except HTTPError as error:
            if response.status_code == 400:
                raise CredentialsBadRequestError(
                    f"Authentication failed with status code 400 Bad Request: {response.json().get('error')}"
                ) from error
            raise
