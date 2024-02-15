"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import os
import re
from collections import defaultdict
from itertools import count
from pathlib import Path
from string import Template
from typing import Tuple
from urllib.parse import urlparse

import requests
from attrs import define, field, validators
from requests import Response, Session
from requests.auth import HTTPBasicAuth

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
    """Get files from an api or simple web server.

    Matching string examples:

    * Simple http target: :code:`http://your.target/file.yml`
    * Simple https target: :code:`https://your.target/file.json`

    If you want to use basic auth, then you have to set the environment variables:

        * :code:`LOGPREP_CONFIG_AUTH_USERNAME=<your_username>`
        * :code:`LOGPREP_CONFIG_AUTH_PASSWORD=<your_password>`

    If you want to use oauth, then you have to set the environment variables:

        * :code:`LOGPREP_CONFIG_AUTH_TOKEN=<your_token>`
        * :code:`LOGPREP_CONFIG_AUTH_METHOD=oauth`

    If you want to load multiple resources from different sources you can set multiple auth tokens
    by appending a strictly monotonously rising index to the variable. For example by using
    :code:`LOGPREP_CONFIG_AUTH_TOKEN_0`, :code:`LOGPREP_CONFIG_AUTH_TOKEN_1`,
    :code:`LOGPREP_CONFIG_AUTH_TOKEN_2`, etc. Logprep always tries to use all token until one is
    successful.
    """

    _sessions: dict = {}

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
        if os.environ.get("LOGPREP_CONFIG_AUTH_METHOD") == "oauth":
            self._username = None
            self._password = None
            if token := os.environ.get("LOGPREP_CONFIG_AUTH_TOKEN"):
                self._tokens.append(token)
            for token_index in count(start=0, step=1):
                if token := os.environ.get(f"LOGPREP_CONFIG_AUTH_TOKEN_{token_index}"):
                    self._tokens.append(token)
                    continue
                break
        self._username = os.environ.get("LOGPREP_CONFIG_AUTH_USERNAME")
        self._password = os.environ.get("LOGPREP_CONFIG_AUTH_PASSWORD")

    def get_raw(self) -> bytearray:
        """gets the content from a http server via uri"""
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
        retries = 3
        resp = None
        while resp is None:
            try:
                if not self._found_valid_token:
                    resp = self._search_for_valid_token(session, url)
                else:
                    resp = self._execute_request(session, url)
            except requests.exceptions.RequestException as error:
                retries -= 1
                if retries == 0:
                    raise error
        resp.raise_for_status()
        return resp.content

    def _search_for_valid_token(self, session: Session, url: str) -> [Response, None]:
        for token in self._tokens:
            self._headers.update({"Authorization": f"Bearer {token}"})
            resp = self._execute_request(session, url)
            if resp is not None and resp.status_code == 200:
                self._found_valid_token = True
                return resp
        return None

    def _execute_request(self, session: Session, url: str) -> [Response, None]:
        return session.get(url=url, timeout=5, allow_redirects=True, headers=self._headers)
