"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import os
import re
import sys
from collections import defaultdict
from itertools import count
from pathlib import Path
from string import Template
from typing import Tuple
from urllib.parse import urlparse

import requests
from attrs import define, field, validators
from requests import Session, Response
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from schedule import Scheduler
from urllib3 import Retry

from logprep._version import get_versions
from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter


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
    """get files from a api or simple web server.

    Matching string examples:

    * Simple http target: :code:`http://your.target/file.yml`
    * Simple https target: :code:`https://your.target/file.json`

    if you want to use basic auth, then you have to set the environment variables

        * :code:`LOGPREP_CONFIG_AUTH_USERNAME=<your_username>`
        * :code:`LOGPREP_CONFIG_AUTH_PASSWORD=<your_password>`

    if you want to use oauth, then you have to set the environment variables

        * :code:`LOGPREP_CONFIG_AUTH_TOKEN=<your_token>`
        * :code:`LOGPREP_CONFIG_AUTH_METHOD=oauth`

    """

    _sessions: dict = {}
    _scheduler = Scheduler()

    _username: str = field(validator=validators.optional(validators.instance_of(str)), default=None)
    _password: str = field(validator=validators.optional(validators.instance_of(str)), default=None)
    _headers: dict = field(validator=validators.instance_of(dict), factory=dict)
    _found_valid_token: bool = field(default=False)
    _tokens: list[str] = field(factory=list)

    def __attrs_post_init__(self):
        user_agent = f"Logprep version {get_versions().get('version')}"
        self._headers |= {"User-Agent": user_agent}
        target = self.target
        target_match = re.match(r"^((?P<username>.+):(?P<password>.+)@)?(?P<target>.+)", target)
        self.target = target_match.group("target")
        if target_match.group("username") or target_match.group("password"):
            raise NotImplementedError(
                "Basic auth credentials via commandline are not supported."
                "Please use environment variables "
                "LOGPREP_CONFIG_AUTH_USERNAME and LOGPREP_CONFIG_AUTH_PASSWORD instead."
            )
        self._set_credentials()

    def _set_credentials(self):
        if os.environ.get("LOGPREP_OAUTH2_0_ENDPOINT") is not None:
            self._get_oauth_token()
        else:
            self._username = os.environ.get("LOGPREP_CONFIG_AUTH_USERNAME")
            self._password = os.environ.get("LOGPREP_CONFIG_AUTH_PASSWORD")

    def _get_oauth_token(self):
        min_expires_in = sys.maxsize
        for i in count(start=0, step=1):
            if os.environ.get(f"LOGPREP_OAUTH2_{i}_ENDPOINT") is None:
                break
            endpoint = os.environ.get(f"LOGPREP_OAUTH2_{i}_ENDPOINT")
            grant_type = os.environ.get(f"LOGPREP_OAUTH2_{i}_GRANT_TYPE")
            username = os.environ.get(f"LOGPREP_OAUTH2_{i}_USERNAME")
            password = os.environ.get(f"LOGPREP_OAUTH2_{i}_PASSWORD")
            client_id = os.environ.get(f"LOGPREP_OAUTH2_{i}_CLIENT_ID")
            client_secret = os.environ.get(f"LOGPREP_OAUTH2_{i}_CLIENT_SECRET")
            payload = {"grant_type": grant_type, "username": username, "password": password}
            if client_id is not None and client_secret is not None:
                payload.update({"client_id": client_id, "client_secret": client_secret})
            response = requests.post(url=endpoint, data=payload, timeout=1)
            token_response = response.json()
            self._tokens.append(token_response.get("access_token"))
            if token_response.get("expires_in") < min_expires_in:
                min_expires_in = token_response.get("expires_in")
        self._scheduler.every(min_expires_in).seconds.do(self._get_oauth_token)
        self._found_valid_token = False

    def get_raw(self) -> bytearray:
        """gets the content from a http server via uri"""
        self._scheduler.run_pending()
        basic_auth = None
        username, password = self._username, self._password
        if username is not None:
            basic_auth = HTTPBasicAuth(username, password)
        url = f"{self.protocol}://{self.target}"
        domain = urlparse(url).netloc
        if domain not in self._sessions:
            domain_session = requests.Session()
            self._sessions.update({domain: domain_session})
        session = self._sessions.get(domain)
        if basic_auth:
            session.auth = basic_auth
        if not self._found_valid_token and self._tokens:
            self._get_valid_token(session, url)
            self._found_valid_token = True
        retries = Retry(total=3, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.mount("http://", HTTPAdapter(max_retries=retries))
        resp = self._execute_request(session, url)
        resp.raise_for_status()
        return resp.content

    def _get_valid_token(self, session: Session, url: str):
        errors = []
        for token in self._tokens:
            self._headers.update({"Authorization": f"Bearer {token}"})
            try:
                resp = self._execute_request(session, url)
                resp.raise_for_status()
                return
            except requests.HTTPError as error:
                errors.append(error)
        raise requests.exceptions.RequestException(
            f"No valid token found due to following Errors: {errors}"
        )

    def _execute_request(self, session: Session, url: str) -> Response:
        return session.get(url=url, timeout=5, allow_redirects=True, headers=self._headers)
