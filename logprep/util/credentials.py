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

    endpoint: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))
    username: str = field(validator=validators.instance_of(str))
    _timeout: int = field(validator=validators.instance_of(int), default=1)

    def get_session(self) -> Session:
        token = self._get_token()
        session = super().get_session()
        session.headers["Authorization"] = f"Bearer {token}"
        return session

    def _get_token(self):
        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        response = requests.post(url=self.endpoint, data=payload, timeout=self._timeout)
        token_response = response.json()
        return token_response.get("access_token")


@define(kw_only=True)
class OAuth2ClientFlowCredentials(Credentials):

    endpoint: str = field(validator=validators.instance_of(str))
    client_id: str = field(validator=validators.instance_of(str))
    client_secret: str = field(validator=validators.instance_of(str))

    def get_session(self) -> Session:
        raise NotImplementedError
