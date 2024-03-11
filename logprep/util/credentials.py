from base64 import b64encode

import requests
from attrs import define, field, validators
from requests import Session

from logprep.abc.credentials import Credentials


@define(kw_only=True)
class BasicAuthCredentials(Credentials):

    username: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))

    def get_session(self) -> Session:
        session = super().get_session()
        session.auth = (self.username, self.password)
        return session


@define(kw_only=True)
class OAuth2TokenCredentials(Credentials):

    token: str = field(validator=validators.instance_of(str))

    def get_session(self) -> Session:
        session = super().get_session()
        session.headers["Authorization"] = f"Bearer {self.token}"
        return session


@define(kw_only=True)
class OAuth2PasswordFlowCredentials(Credentials):
    """OAuth2 Resource Owner Password Credentials Grant
    https://datatracker.ietf.org/doc/html/rfc6749#section-4.3
    """

    endpoint: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))
    username: str = field(validator=validators.instance_of(str))
    _timeout: int = field(validator=validators.instance_of(int), default=1)
    """the timeout for the token request"""

    def get_session(self) -> Session:
        access_token, refresh_token, expires_in = self._get_token()
        # TODO: implement refresh token
        session = super().get_session()
        session.headers["Authorization"] = f"Bearer {access_token}"
        return session

    def _get_token(self) -> tuple[str, str, int]:
        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        response = requests.post(
            url=self.endpoint,
            data=payload,
            timeout=self._timeout,
        )
        token_response = response.json()
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")
        return access_token, refresh_token, expires_in


@define(kw_only=True)
class OAuth2ClientFlowCredentials(Credentials):
    """OAuth2 Client Credentials Flow Implementation as described in
    https://datatracker.ietf.org/doc/html/rfc6749#section-1.3.4
    """

    endpoint: str = field(validator=validators.instance_of(str))
    client_id: str = field(validator=validators.instance_of(str))
    client_secret: str = field(validator=validators.instance_of(str))
    _timeout: int = field(validator=validators.instance_of(int), default=1)

    def get_session(self) -> Session:
        access_token, refresh_token, expires_in = self._get_token()
        # TODO: implement refresh token
        session = super().get_session()
        session.headers["Authorization"] = f"Bearer {access_token}"
        return session

    def _get_token(self) -> tuple[str, str, int]:
        payload = {
            "grant_type": "client_credentials",
        }
        client_secrets = b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode(
            "utf-8"
        )
        headers = {"Authorization": f"Basic {client_secrets}"}
        response = requests.post(
            url=self.endpoint,
            data=payload,
            timeout=self._timeout,
            headers=headers,
        )
        token_response = response.json()
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")
        return access_token, refresh_token, expires_in
