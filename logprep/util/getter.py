"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import json
import logging
import os
import re
from collections import defaultdict
from functools import cached_property, reduce
from itertools import count
from pathlib import Path
from string import Template
from typing import Tuple
from urllib.parse import urlparse

import requests
from attrs import define, field, validators
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from ruamel.yaml.error import YAMLError
from urllib3 import Retry

from logprep._version import get_versions
from logprep.abc.credentials import Credentials
from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter
from logprep.factory_error import InvalidConfigurationError
from logprep.util.credentials import (
    BasicAuthCredentials,
    OAuth2ClientFlowCredentials,
    OAuth2PasswordFlowCredentials,
    OAuth2TokenCredentials,
)


class GetterNotFoundError(LogprepException):
    """Is raised if getter is not found."""

    def __init__(self, message) -> None:
        if message:
            super().__init__(message)


class GetterFactory:
    """Provides methods to create getters."""

    @classmethod
    def from_string(cls, getter_string: str) -> "Getter":
        """Factory method to return a getter from a string in format :code:`<protocol>://<target>`.
        If no protocol is given, then the file protocol is assumed.

        Parameters
        ----------
        getter_string : str
            A string describing the getter protocol and target information.

        Returns
        -------
        Getter
            The generated getter.
        """
        protocol, target = cls._dissect(getter_string)
        target = cls._expand_variables(target, os.environ)
        # get credentials
        if protocol is None:
            protocol = "file"
        if protocol == "file":
            return FileGetter(protocol=protocol, target=target)
        if protocol == "http":
            return HttpGetter(protocol=protocol, target=target)
        if protocol == "https":
            return HttpGetter(protocol=protocol, target=target)
        raise GetterNotFoundError(f"No getter for protocol '{protocol}'")

    @staticmethod
    def _expand_variables(posix_expr, context):
        env = defaultdict(lambda: "")
        env.update(context)
        return Template(posix_expr).substitute(env)

    @staticmethod
    def _dissect(getter_string: str) -> Tuple[str, str]:
        regexp = r"^((?P<protocol>[^\s]+)://)?(?P<target>.+)"
        matches = re.match(regexp, getter_string)
        return matches.group("protocol"), matches.group("target")


@define(kw_only=True)
class FileGetter(Getter):
    """Get files (and only files) from a filesystem.

    Matching string examples:

    * :code:`/yourpath/yourfile.extension`
    * :code:`file://yourpath/yourfile.extension`

    """

    def get_raw(self) -> bytearray:
        """Opens file and returns its binary content."""
        return Path(self.target).read_bytes()


@define(kw_only=True)
class HttpGetter(Getter):
    """Get files from an api or simple web server.

    Matching string examples:

    * Simple http target: :code:`http://your.target/file.yml`
    * Simple https target: :code:`https://your.target/file.json`

    In order for Logprep to choose the correct authentication method the `LOGPREP_CREDENTIALS_FILE` environment variable has to be set.
    This file should provide the credentials that are needed and can either be in yaml or in json format.
    To use the authentication, the `LOGPREP_CREDENTIALS_FILE` file has to be filled with the correct values that correspond to the method you want to use.
    The following authentication methods are implemented:

    - OAuth authentication with known token:
    ```yaml
        "http://ressource":
            token_file: <path/to/token/file>
    ```
    - OAuth client authorization grant:
    ```yaml
    "http://ressource":
        endpoint: <endpoint>
        client_id: <id>
        client_secret_file: <path/to/secret/file>
    ```
    - OAuth password grand type:
    ```yaml
    "http://ressource":
        endpoint: <endpoint>
        username: <username>
        password_file: <path/to/password/file>
    ```
    - Basic Authentication
    ```yaml
    "http://ressource":
        username: <username>
        password_file: <path/to/password/file>
    ```
    """

    _sessions: dict = {}

    _headers: dict = field(validator=validators.instance_of(dict), factory=dict)

    def __attrs_post_init__(self):
        user_agent = f"Logprep version {get_versions().get('version')}"
        self._headers |= {"User-Agent": user_agent}
        target = self.target
        target_match = re.match(r"^((?P<username>.+):(?P<password>.+)@)?(?P<target>.+)", target)
        self.target = target_match.group("target")
        if target_match.group("username") or target_match.group("password"):
            raise NotImplementedError(
                "Basic auth credentials via commandline are not supported."
                "Please use the credential file in connection with the "
                "environment variable 'LOGPREP_CREDENTIALS_FILE' to authenticate."
            )

    @cached_property
    def credentials(self) -> Credentials:
        """get credentials for target from environment variable LOGPREP_CREDENTIALS_FILE"""
        credentials_file_path = os.environ.get("LOGPREP_CREDENTIALS_FILE")
        if credentials_file_path is None:
            return None
        all_credentials = self._get_content(credentials_file_path)
        url = f"{self.protocol}://{self.target}"
        domain = urlparse(url).netloc
        raw_credentials = all_credentials.get(f"{self.protocol}://{domain}")
        if raw_credentials:
            if "client_secret_file" in raw_credentials:
                raw_credentials.update({"client_secret": self._get_secret_content(raw_credentials)})
            if "token_file" in raw_credentials:
                raw_credentials.update({"token": self._get_secret_content(raw_credentials)})
            if "password_file" in raw_credentials:
                raw_credentials.update({"password": self._get_secret_content(raw_credentials)})
        credentials = self._get_credentials_from_resource(raw_credentials)
        return credentials

    def _get_content(self, file_path):
        try:
            getter = GetterFactory.from_string(file_path)
            try:
                file_content = getter.get_json()
            except (json.JSONDecodeError, ValueError):
                file_content = getter.get_yaml()
        except (TypeError, YAMLError) as error:
            raise InvalidConfigurationError(
                f"Invalid credentials file: {file_path} {error.args[0]}"
            ) from error
        except FileNotFoundError as error:
            raise InvalidConfigurationError(
                f"Environment variable has wrong credentials file path: {file_path}"
            ) from error
        return file_content

    def _get_secret_content(self, resource: dict):
        """gets content from given secret_file"""

        for key, value in resource.items():
            if "_file" in key or "_file" in value:
                file_path = value
                getter = GetterFactory.from_string(str(file_path))
                file_content = getter.get_raw().decode("utf-8")
                return file_content

    def _get_credentials_from_resource(self, resource: dict) -> Credentials:
        """matches the given credentials of the resource with the expected credential object"""
        logger = logging.getLogger()
        try:
            match resource:
                case {"token": token, **extra_params}:
                    if extra_params:
                        logger.warning(
                            "Other parameters were given: %s but OAuth token authorization was chosen",
                            extra_params,
                        )
                    return OAuth2TokenCredentials(token=token)
                case {
                    "endpoint": endpoint,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    **extra_params,
                }:
                    if extra_params:
                        logger.warning(
                            "Other parameters were given: %s but OAuth client authorization was chosen",
                            extra_params,
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
                        logger.warning(
                            "Other parameters were given: %s but OAuth password authorization was chosen",
                            extra_params,
                        )
                    return OAuth2PasswordFlowCredentials(
                        endpoint=endpoint, username=username, password=password
                    )
                case {"username": username, "password": password, **extra_params}:
                    if extra_params:
                        logger.warning(
                            "Other parameters were given but Basic authentication was chosen: %s",
                            extra_params,
                        )
                    return BasicAuthCredentials(username=username, password=password)
                case _:
                    logger.warning("No matching credentials authentication could be found.")
                    return None
        except TypeError as error:
            raise InvalidConfigurationError(
                f"Wrong type in given credentials file on argument: {error.args[0]}"
            ) from error

    def get_raw(self) -> bytearray:
        """gets the content from a http server via uri"""
        url = f"{self.protocol}://{self.target}"
        domain = urlparse(url).netloc
        if domain not in self._sessions:
            if self.credentials is None:
                self._sessions.update({domain: requests.Session()})
            else:
                self._sessions.update({domain: self.credentials.get_session()})
        session: Session = self._sessions.get(domain)
        max_retries = 3
        retries = Retry(total=max_retries, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.mount("http://", HTTPAdapter(max_retries=retries))
        resp = session.get(url=url, timeout=5, allow_redirects=True, headers=self._headers)
        resp.raise_for_status()
        return resp.content
