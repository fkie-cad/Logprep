from base64 import b64encode
from datetime import datetime, timedelta

import requests
from attrs import define, field, validators
from requests import Session

from logprep.abc.credentials import Credentials


@define(kw_only=True)
class AccessToken:
    """A simple dataclass to hold the token and its expiry time."""

    token: str = field(validator=validators.instance_of(str))
    refresh_token: str = field(validator=validators.instance_of((str, type(None))), default=None)
    expires_in: int = field(
        validator=validators.instance_of(int),
        default=0,
        converter=lambda x: 0 if x is None else int(x),
    )
    expiry_time: datetime = field(
        validator=validators.instance_of((datetime, type(None))), init=False
    )

    def __attrs_post_init__(self):
        self.expiry_time = datetime.now() + timedelta(seconds=self.expires_in)

    def __str__(self) -> str:
        return self.token

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_in == 0:
            return False
        return datetime.now() > self.expiry_time


@define(kw_only=True)
class BasicAuthCredentials(Credentials):
    """Basic Authentication Credentials"""

    username: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))

    def get_session(self) -> Session:
        session = super().get_session()
        session.auth = (self.username, self.password)
        return session


@define(kw_only=True)
class OAuth2TokenCredentials(Credentials):
    """OAuth2 Bearer Token Credentials
    This is used for authenticating with an API that uses OAuth2 Bearer Tokens.
    The Token is not refreshed automatically. If it expires, the requests will
    fail with http status code `401`.
    """

    token: AccessToken = field(
        validator=validators.instance_of(AccessToken),
        converter=lambda token: AccessToken(token=token),
    )
    """The OAuth2 Bearer Token. This is used to authenticate."""

    def get_session(self) -> Session:
        session = super().get_session()
        session.headers["Authorization"] = f"Bearer {self.token}"
        return session


@define(kw_only=True)
class OAuth2PasswordFlowCredentials(Credentials):
    """OAuth2 Resource Owner Password Credentials Grant as described in
    https://datatracker.ietf.org/doc/html/rfc6749#section-4.3

    Token refresh is implemented as described in
    https://datatracker.ietf.org/doc/html/rfc6749#section-6
    """

    endpoint: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))
    username: str = field(validator=validators.instance_of(str))
    timeout: int = field(validator=validators.instance_of(int), default=1)
    """the timeout for the token request"""
    _token: AccessToken = field(
        validator=validators.instance_of((AccessToken, type(None))),
        init=False,
    )

    def get_session(self) -> Session:
        session = super().get_session()
        payload = None
        if self._no_authorization_header(session):
            payload = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
            session.headers["Authorization"] = f"Bearer {self._get_token(payload)}"

        if self._token.is_expired and self._token.refresh_token is not None:
            session = Session()
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self._token.refresh_token,
            }
            session.headers["Authorization"] = f"Bearer {self._get_token(payload)}"
        self._session = session
        return session

    def _get_token(self, payload: dict[str, str]) -> AccessToken:
        response = requests.post(
            url=self.endpoint,
            data=payload,
            timeout=self.timeout,
        )
        self._handle_bad_requests_errors(response)
        token_response = response.json()
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")
        self._token = AccessToken(
            token=access_token, refresh_token=refresh_token, expires_in=expires_in
        )
        return self._token


@define(kw_only=True)
class OAuth2ClientFlowCredentials(Credentials):
    """OAuth2 Client Credentials Flow Implementation as described in
    https://datatracker.ietf.org/doc/html/rfc6749#section-1.3.4
    """

    endpoint: str = field(validator=validators.instance_of(str))
    client_id: str = field(validator=validators.instance_of(str))
    client_secret: str = field(validator=validators.instance_of(str))
    timeout: int = field(validator=validators.instance_of(int), default=1)
    _token: AccessToken = field(
        validator=validators.instance_of((AccessToken, type(None))),
        init=False,
    )

    def get_session(self) -> Session:
        session = super().get_session()
        if "Authorization" in session.headers and self._token.is_expired:
            session = Session()
        if self._no_authorization_header(session):
            session.headers["Authorization"] = f"Bearer {self._get_token()}"
        return session

    def _get_token(self) -> AccessToken:
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
            timeout=self.timeout,
            headers=headers,
        )
        self._handle_bad_requests_errors(response)
        token_response = response.json()
        access_token = token_response.get("access_token")
        expires_in = token_response.get("expires_in")
        self._token = AccessToken(token=access_token, expires_in=expires_in)
        return self._token
