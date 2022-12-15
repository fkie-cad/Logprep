"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""
import os
import re
from collections import defaultdict
from pathlib import Path
from string import Template
from typing import Tuple

import requests
from requests.auth import HTTPBasicAuth

from logprep._version import get_versions
from logprep.abc.getter import Getter


class GetterNotFoundError(BaseException):
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


class FileGetter(Getter):
    """Get files (and only files) from a filesystem.

    Matching string examples:

    * :code:`/yourpath/yourfile.extension`
    * :code:`file://yourpath/yourfile.extension`

    """

    def get(self) -> str:
        """Opens file (with utf8 encoding) and returns its content."""
        return Path(self.target).read_text(encoding="utf8")


class HttpGetter(Getter):
    """get files from a api or simple web server.

    Matching string examples:

    * Simple http target: :code:`http://your.target/file.yml`
    * Simple https target: :code:`https://your.target/file.json`
    * Target with asic authentication: :code:`https://username:password@your_web_target`
    * Target with oauth compliant authentication with bearer token header:
      :code:`https://oauth:<your bearer token>@your_web_target`

    """

    def get(self) -> str:
        """gets the content from a http server via uri"""
        user_agent = f"Logprep version {get_versions().get('version')}"
        headers = {"User-Agent": user_agent}
        basic_auth = None
        target = self.target

        auth_match = re.match(r"^((?P<username>.+):(?P<password>.+)@)?(?P<target>.+)", target)
        target = auth_match.group("target")
        username = auth_match.group("username")
        password = auth_match.group("password")

        if username == "oauth":
            headers.update({"Authorization": f"Bearer {password}"})
        if username is not None and username != "oauth":
            basic_auth = HTTPBasicAuth(username, password)

        resp = requests.get(
            url=f"{self.protocol}://{target}",
            timeout=5,
            allow_redirects=True,
            headers=headers,
            auth=basic_auth,
        )
        resp.raise_for_status()
        content = resp.text
        return content
