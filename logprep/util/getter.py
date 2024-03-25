"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from string import Template
from typing import Tuple
from urllib.parse import urlparse

from attrs import define, field, validators

from logprep._version import get_versions
from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter
from logprep.util.credentials import Credentials, CredentialsFactory


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

    .. automodule:: logprep.util.credentials
        :no-index:

    """

    _credentials_registry: dict[str, Credentials] = {}

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

    @property
    def url(self) -> str:
        """Returns the url of the target."""
        return f"{self.protocol}://{self.target}"

    @property
    def credentials(self) -> Credentials:
        """get credentials for target from environment variable LOGPREP_CREDENTIALS_FILE"""
        creds = None
        if "LOGPREP_CREDENTIALS_FILE" in os.environ:
            creds = CredentialsFactory.from_target(self.url)
        return creds if creds else Credentials()

    def get_raw(self) -> bytearray:
        """gets the content from a http server via uri"""
        domain = urlparse(self.url).netloc
        scheme = urlparse(self.url).scheme
        domain_uri = f"{scheme}://{domain}"
        if domain_uri not in self._credentials_registry:
            self._credentials_registry.update({domain_uri: self.credentials})
        session = self._credentials_registry.get(domain_uri).get_session()
        resp = session.get(url=self.url, timeout=5, allow_redirects=True, headers=self._headers)
        resp.raise_for_status()
        return resp.content
