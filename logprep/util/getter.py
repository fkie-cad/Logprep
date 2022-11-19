"""module for content getters"""
import re
import requests
from requests.auth import HTTPBasicAuth
from typing import Tuple
from pathlib import Path
from logprep.abc.getter import Getter
from logprep._version import get_versions


class GetterNotFoundError(BaseException):
    """is raised if getter is not found"""

    def __init__(self, message) -> None:
        if message:
            super().__init__(message)


class GetterFactory:
    """provides methods to create getters"""

    @classmethod
    def from_string(cls, getter_string: str) -> "FileGetter":
        """factory method to get a getter

        Parameters
        ----------
        getter_string : str
            a string describing the getter protocol and target informations

        Returns
        -------
        Getter
            the generated getter
        """
        protocol, target = cls._dissect(getter_string)
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
    def _dissect(getter_string: str) -> Tuple[str, str]:
        regexp = r"^((?P<protocol>[^\s]+)://)?(?P<target>.+)"
        matches = re.match(regexp, getter_string)
        return matches.group("protocol"), matches.group("target")


class FileGetter(Getter):
    """FileIO getter"""

    def get(self):
        """opens file and returns its content"""
        return Path(self.target).read_text(encoding="utf8")


class HttpGetter(Getter):
    """Http getter"""

    def get(self):
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
