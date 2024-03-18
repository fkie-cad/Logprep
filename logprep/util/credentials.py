"""
Authentication
==============

In order for Logprep to choose the correct authentication method the
`LOGPREP_CREDENTIALS_FILE` environment variable has to be set.
This file should provide the credentials that are needed and can either be
in yaml or in json format.
To use the authentication, the `LOGPREP_CREDENTIALS_FILE` file has to be
filled with the correct values that correspond to the method you want to use.

some example entries for such a credentials file notation are:

```yaml
"http://ressource":
    token_file: <path/to/token/file> # won't be refreshed if expired
"http://ressource":
    # example for OAuth2 Client Credentials Grant
    endpoint: <endpoint>
    client_id: <id>
    client_secret_file: <path/to/secret/file>
"http://ressource":
    # example for OAuth2 Resource Owner Password Credentials Grant
    endpoint: <endpoint>
    username: <username>
    password_file: <path/to/password/file>
    client_id: <client_id> # optional
    client_secret_file: <path/to/secret/file> # optional
"http://ressource":
    # example for Basic Authentication
    username: <username>
    password_file: <path/to/password/file>
"http://ressource":
    # example for Basic Authentication with inline password
    username: <username>
    password: <plaintext password> # will be overwritten if 'password_file' is given
```
Authentication Process: 
.. raw:: html
   :file: ../../development/architecture/diagramms/Credentials.drawio.html

"""

import json
import logging
import os
from base64 import b64encode
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from attrs import define, field, validators
from requests import HTTPError, Session
from requests.adapters import HTTPAdapter
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from urllib3 import Retry

from logprep.factory_error import InvalidConfigurationError

yaml = YAML(typ="safe", pure=True)


class CredentialsBadRequestError(Exception):
    """Raised when the API returns a 400 Bad Request error"""


class CredentialsFactory:
    """Factory class to create credentials from a given target URL."""

    _logger = logging.getLogger(__name__)

    @classmethod
    def from_target(cls, target_url: str) -> "Credentials":
        """Factory method to create a credentials object based on the given target from
            env variable `LOGPREP_CREDENTIALS_FILE`

        Parameters
        ----------
        target_url : str
            target for which credentials are used

        Returns
        -------
        credentials: Credentials
            Credentials object representing the correct authorization
            depending on the given credentials
        """
        credentials_file_path = os.environ.get("LOGPREP_CREDENTIALS_FILE")
        if credentials_file_path is None:
            return None
        raw_content: dict = cls._get_content(Path(credentials_file_path))
        domain = urlparse(target_url).netloc
        scheme = urlparse(target_url).scheme
        raw_credentials = raw_content.get(f"{scheme}://{domain}")
        if raw_credentials:
            cls._get_secret_content(raw_credentials)
        credentials = cls._get_credentials_from_mapping(raw_credentials)
        return credentials

    @staticmethod
    def _get_content(file_path: Path) -> dict:
        """gets content from credentials file
        file can be either json or yaml

        Parameters
        ----------
        file_path : Path
            path to credentials file given in `LOGPREP_CREDENTIALS_FILE`

        Returns
        -------
        file_content: dict
            content from file

        Raises
        ------
        InvalidConfigurationError
            raises when credentials have wrong type or when credentials file
            is invalid
        """
        try:
            file_content = file_path.read_text(encoding="utf-8")
            try:
                return json.loads(file_content)
            except (json.JSONDecodeError, ValueError):
                return yaml.load(file_content)
        except (TypeError, YAMLError) as error:
            raise InvalidConfigurationError(
                f"Invalid credentials file: {file_path} {error.args[0]}"
            ) from error
        except FileNotFoundError as error:
            raise InvalidConfigurationError(
                f"Environment variable has wrong credentials file path: {file_path}"
            ) from error

    @staticmethod
    def _get_secret_content(credential_mapping: dict):
        """gets content from given secret_file in credentials file and updates
        credentials_mapping with this content.

        This file should only contain the content of the given secret e.g. the client secret.

        Parameters
        ----------
        credentials_mapping : dict
            content from given credentials mapping
        """
        secret_content = {
            credential_type.removesuffix("_file"): Path(credential_content).read_text(
                encoding="utf-8"
            )
            for credential_type, credential_content in credential_mapping.items()
            if "_file" in credential_type
        }
        for credential_type in secret_content:
            credential_mapping.pop(f"{credential_type}_file")
        credential_mapping.update(secret_content)

    @classmethod
    def _get_credentials_from_mapping(cls, credential_mapping: dict) -> "Credentials":
        """matches the given credentials of the credentials mapping with the expected credential object"""
        try:
            return cls._match_credentials(credential_mapping)
        except TypeError as error:
            raise InvalidConfigurationError(
                f"Wrong type in given credentials file on argument: {error.args[0]}"
            ) from error

    @classmethod
    def _match_credentials(cls, credential_mapping: dict) -> "Credentials":
        """matches the given credentials of a given mapping to the expected credential object

        Parameters
        ----------
        credential_mapping : dict
            mapping of given credentials

        Returns
        -------
        Credentials
           expected credentials object representing the correct authentication method
        """
        match credential_mapping:
            case {"token": token, **extra_params}:
                if extra_params:
                    cls._logger.warning(
                        "Other parameters were given: %s but OAuth token authorization was chosen",
                        extra_params.keys(),
                    )
                return OAuth2TokenCredentials(token=token)
            case {
                "endpoint": endpoint,
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
                **extra_params,
            }:
                if extra_params:
                    cls._logger.warning(
                        "Other parameters were given: %s but OAuth client authorization was chosen",
                        extra_params.keys(),
                    )
                return OAuth2PasswordFlowCredentials(
                    endpoint=endpoint,
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                )
            case {
                "endpoint": endpoint,
                "client_id": client_id,
                "client_secret": client_secret,
                **extra_params,
            }:
                if extra_params:
                    cls._logger.warning(
                        "Other parameters were given: %s but OAuth client authorization was chosen",
                        extra_params.keys(),
                    )
                return OAuth2ClientFlowCredentials(
                    endpoint=endpoint, client_id=client_id, client_secret=client_secret
                )
            case {
                "endpoint": endpoint,
                "username": username,
                "password": password,
                **extra_params,
            }:
                if extra_params:
                    cls._logger.warning(
                        "Other parameters were given: %s but OAuth password authorization was chosen",
                        extra_params.keys(),
                    )
                return OAuth2PasswordFlowCredentials(
                    endpoint=endpoint, username=username, password=password
                )
            case {"username": username, "password": password, **extra_params}:
                if extra_params:
                    cls._logger.warning(
                        "Other parameters were given but Basic authentication was chosen: %s",
                        extra_params.keys(),
                    )
                return BasicAuthCredentials(username=username, password=password)
            case _:
                cls._logger.warning("No matching credentials authentication could be found.")
                return None


@define(kw_only=True)
class AccessToken:
    """A simple dataclass to hold the token and its expiry time."""

    token: str = field(validator=validators.instance_of(str), repr=False)
    refresh_token: str = field(
        validator=validators.instance_of((str, type(None))), default=None, repr=False
    )
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
class Credentials:
    """Abstract Base Class for Credentials"""

    _logger = logging.getLogger(__name__)

    _session: Session = field(validator=validators.instance_of((Session, type(None))), default=None)

    def get_session(self):
        """Return a session and mount HTTPAdapter"""
        if self._session is None:
            self._session = Session()
            max_retries = 3
            retries = Retry(total=max_retries, status_forcelist=[500, 502, 503, 504])
            self._session.mount("https://", HTTPAdapter(max_retries=retries))
            self._session.mount("http://", HTTPAdapter(max_retries=retries))
        return self._session

    def _no_authorization_header(self, session):
        """checks if authorization header exists in session"""
        return session.headers.get("Authorization") is None

    def _handle_bad_requests_errors(self, response):
        """handles bad requests and raises CredentialsBadRequestError

        Parameters
        ----------
        response : Response
            respone from post request while getting the token

        Raises
        ------
        CredentialsBadRequestError
            raises error with status code 400
        """
        try:
            response.raise_for_status()
        except HTTPError as error:
            if response.status_code == 400:
                raise CredentialsBadRequestError(
                    f"Authentication failed with status code 400 Bad Request: {response.json().get('error')}"
                ) from error
            raise


@define(kw_only=True)
class BasicAuthCredentials(Credentials):
    """Basic Authentication Credentials"""

    username: str = field(validator=validators.instance_of(str))
    """The username for the basic authentication."""
    password: str = field(validator=validators.instance_of(str), repr=False)
    """The password for the basic authentication."""

    def get_session(self) -> Session:
        """gets session with basic authentication

        Returns
        -------
        session: Session
            session with username and password set for authentication
        """
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
        repr=False,
    )
    """The OAuth2 Bearer Token. This is used to authenticate."""

    def get_session(self) -> Session:
        """gets session with token in the authorization header"""
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
    """The token endpoint for the OAuth2 server. This is used to request the token."""
    password: str = field(validator=validators.instance_of(str), repr=False)
    """the password for the token request"""
    username: str = field(validator=validators.instance_of(str))
    """the username for the token request"""
    timeout: int = field(validator=validators.instance_of(int), default=1)
    """The timeout for the token request. Defaults to 1 second."""
    client_id: str = field(validator=validators.instance_of((str, type(None))), default=None)
    """The client id for the token request. This is used to identify the client. (Optional)"""
    client_secret: str = field(
        validator=validators.instance_of((str, type(None))), default=None, repr=False
    )
    """The client secret for the token request. This is used to authenticate the client. (Optional)"""
    _token: AccessToken = field(
        validator=validators.instance_of((AccessToken, type(None))),
        init=False,
        repr=False,
    )

    def get_session(self) -> Session:
        """gets session with token in authorization header if token is expired
        the refresh token is used
        """
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
        """gets token from given token endpoint

        Parameters
        ----------
        payload : dict[str, str]
            contains credentials and endpoint from which token should be retrieved
        Returns
        -------
        _token: AccessToken
           returns access token, refresh token and expiry time of given token
        """
        headers = {}
        if self.client_id and self.client_secret:
            client_secrets = b64encode(
                f"{self.client_id}:{self.client_secret}".encode("utf-8")
            ).decode("utf-8")
            headers |= {"Authorization": f"Basic {client_secrets}"}
        response = requests.post(
            url=self.endpoint,
            data=payload,
            timeout=self.timeout,
            headers=headers,
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
    """The token endpoint for the OAuth2 server. This is used to request the token."""
    client_id: str = field(validator=validators.instance_of(str))
    """The client id for the token request. This is used to identify the client."""
    client_secret: str = field(validator=validators.instance_of(str), repr=False)
    """The client secret for the token request. This is used to authenticate the client."""
    timeout: int = field(validator=validators.instance_of(int), default=1)
    """The timeout for the token request. Defaults to 1 second."""
    _token: AccessToken = field(
        validator=validators.instance_of((AccessToken, type(None))), init=False, repr=False
    )

    def get_session(self) -> Session:
        """get session with valid access token in Authorization header

        Returns
        -------
        Session
            session:  Session
        """
        session = super().get_session()
        if "Authorization" in session.headers and self._token.is_expired:
            session = Session()
        if self._no_authorization_header(session):
            session.headers["Authorization"] = f"Bearer {self._get_token()}"
        return session

    def _get_token(self) -> AccessToken:
        """get access token from endpoint using the client credentials grant

        Returns
        -------
        _token: AccessToken
            AccessToken object containing the token
        """
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
