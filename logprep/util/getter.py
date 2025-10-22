"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import json
import logging
import os
import re
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path
from string import Template
from typing import Tuple, ClassVar
from urllib.parse import urlparse

import requests
from requests import Response
from attrs import define, field, validators
from schedule import Scheduler

from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter, yaml
from logprep.util.credentials import (
    Credentials,
    CredentialsEnvNotFoundError,
    CredentialsFactory,
)
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE, ENV_NAME_LOGPREP_GETTER_CONFIG


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
            return FileGetter(protocol=protocol, target=target)  # type: ignore
        if protocol == "http":
            return HttpGetter(protocol=protocol, target=target)  # type: ignore
        if protocol == "https":
            return HttpGetter(protocol=protocol, target=target)  # type: ignore
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
        if matches is None:
            raise GetterNotFoundError(f"Could not parse '{getter_string}'")
        return matches.group("protocol"), matches.group("target")


@define(kw_only=True)
class FileGetter(Getter):
    """Get files (and only files) from a filesystem.

    Matching string examples:

    * :code:`/yourpath/yourfile.extension`
    * :code:`file://yourpath/yourfile.extension`

    """

    def get_raw(self) -> bytes:
        """Opens file and returns its binary content."""
        path = Path(self.target)
        return path.read_bytes()


@define(kw_only=True)
class DataSharedPerTarget:
    """Contains data that is shared for getters with the same target"""

    cache: bytes | None = None

    scheduler: Scheduler | None = None

    refresh_interval: int | None = None

    etag: str | None = None

    callbacks: list = []

    refreshing: bool = False


@define(kw_only=True)
class HttpGetter(Getter):
    """Get files from an api or simple web server.

     Matching string examples:

     * Simple http target: :code:`http://your.target/file.yml`
     * Simple https target: :code:`https://your.target/file.json`

    .. security-best-practice::
       :title: HttpGetter
       :location: any http resource
       :suggested-value: MTLSCredential or OAuth2PasswordFlowCredentials

       If recourses are loaded via HttpGetters it is recommended to

       - use a credential file to securely manage authentication
       - use preferably the :code:`MTLSCredentials` or :code:`OAuth2PasswordFlowCredentials` (with
         client-auth)
       - use always HTTPS connections as HTTPS is not enforced by logprep
       - consider that the HttpGetter does not support pagination. If the resource is provided by
         an endpoint with pagination it could lead to a loss of data.

    .. automodule:: logprep.util.credentials
        :no-index:
    """

    _credentials_registry: dict[str, Credentials] = {}

    _headers: dict = field(validator=validators.instance_of(dict), factory=dict)

    _error = None

    _shared: ClassVar[dict[str, DataSharedPerTarget]] = {}

    _logger = logging.getLogger("console")

    def __attrs_post_init__(self):
        user_agent = f"Logprep version {version('logprep')}"
        self._headers |= {"User-Agent": user_agent}
        target = self.target
        target_match = re.match(r"^((?P<username>.+):(?P<password>.+)@)?(?P<target>.+)", target)
        self.target = target_match.group("target")
        if target_match.group("username") or target_match.group("password"):
            raise NotImplementedError(
                "Basic auth credentials via commandline are not supported."
                "Please use the credential file in connection with the "
                f"environment variable '{ENV_NAME_LOGPREP_CREDENTIALS_FILE}' to authenticate."
            )

        if self._refresh_interval < 0:
            raise ValueError(f"'refresh_interval' must be >= 0: {self._refresh_interval}")
        if self._refresh_interval > 0:
            if self.scheduler is None:
                self.scheduler = Scheduler()
                self.scheduler.every(self._refresh_interval).seconds.do(self._refresh)

    @property
    def shared(self) -> DataSharedPerTarget:
        """Returns the shared data for current target"""
        if self.target not in HttpGetter._shared:
            self.shared = DataSharedPerTarget()
        return HttpGetter._shared[self.target]

    @shared.setter
    def shared(self, value: DataSharedPerTarget) -> None:
        """Set shared data for current target"""
        HttpGetter._shared[self.target] = value

    @property
    def scheduler(self) -> Scheduler:
        """Returns the scheduler for the current target"""
        return self.shared.scheduler

    @scheduler.setter
    def scheduler(self, value: Scheduler) -> None:
        """sets the scheduler for the target"""
        self.shared.scheduler = value

    @property
    def url(self) -> str:
        """Returns the url of the target"""
        return f"{self.protocol}://{self.target}"

    @property
    def etag(self) -> str | None:
        """Returns the etag for the current target"""
        return self.shared.etag

    @etag.setter
    def etag(self, value: str) -> None:
        """Sets the etag for the current target"""
        self.shared.etag = value

    @property
    def cache(self) -> bytes | None:
        """Returns the cache for the current target"""
        return self.shared.cache

    @cache.setter
    def cache(self, value: bytes) -> None:
        """Sets the cache for the current targe"""
        self.shared.cache = value

    @property
    def _callbacks(self) -> list:
        """Returns the callbacks for the current target"""
        return self.shared.callbacks

    @_callbacks.setter
    def _callbacks(self, value: list) -> None:
        """Sets callbacks for the current target"""
        self.shared.callbacks = value

    @property
    def _refresh_interval(self) -> int:
        """Gets the refresh interval for the current target"""
        if self.shared.refresh_interval is None:
            self.shared.refresh_interval = self._get_refresh_interval()
        return self.shared.refresh_interval

    @_refresh_interval.setter
    def _refresh_interval(self, value: int) -> None:
        """Sets the refresh interval for the current target"""
        self.shared.refresh_interval = value

    @property
    def credentials(self) -> Credentials:
        """Get credentials for target from environment variable"""
        creds = None
        if ENV_NAME_LOGPREP_CREDENTIALS_FILE in os.environ:
            creds = CredentialsFactory.from_target(self.url)
        return creds if creds else Credentials()

    def add_callback(self, fnc, *args, **kwargs):
        """Add callbacks to call when http getter refreshes with new data"""
        if self.target not in self._callbacks:
            self._callbacks = []
        self._callbacks.append({"function": fnc, "args": args, "kwargs": kwargs})

    @classmethod
    def add_callback_for_target(cls, target, fnc, *args, **kwargs):
        """Add callbacks to call when http getter with given target refreshes with new data"""
        shared = cls._shared[target]
        if shared is None:
            return
        if target not in shared.callbacks:
            shared.callbacks = []
        shared.callbacks.append({"function": fnc, "args": args, "kwargs": kwargs})

    def _get_refresh_interval(self) -> int:
        """Get refresh interval from a configuration file"""
        if ENV_NAME_LOGPREP_GETTER_CONFIG in os.environ:
            getter_file_path = os.environ.get(ENV_NAME_LOGPREP_GETTER_CONFIG)
            if getter_file_path is None:
                return 0
            getters_config = GetterFactory.from_string(getter_file_path).get_dict()
            return getters_config.get(self.target, {}).get("refresh_interval", 0)
        return 0

    def get_raw(self) -> bytes:
        """Gets the content from cache and update cache if needed"""
        if self._refresh_interval > 0 and self.scheduler:
            self.scheduler.run_pending()
            if self.cache is None:
                try:
                    self._update_cache()
                except requests.exceptions.RequestException as error:
                    raise error
        else:
            try:
                self._update_cache()
            except requests.exceptions.RequestException as error:
                if self.cache is None:
                    raise error
                self._log_cache_warning(error)
        if self.cache is None:
            raise ValueError(f"Cache is empty for http getter with url '{self.url}'")
        return self.cache

    def _log_cache_warning(self, error: Exception):
        self._logger.warning(
            f"Not updating HTTP getter cache with url '{self.url}' due to: %s", error
        )

    def _refresh(self) -> None:
        if self.shared.refreshing:
            return
        self.shared.refreshing = True
        try:
            not_modified = self._update_cache()
        except requests.exceptions.RequestException as error:
            self._log_cache_warning(error)
            not_modified = True
        if not_modified:
            self.shared.refreshing = False
            return
        for callback in self._callbacks:
            callback["function"](*callback["args"], **callback["kwargs"])
        self.shared.refreshing = False

    def _update_cache(self) -> bool:
        response = self._do_request()
        not_modified: bool = response.status_code == 304
        if not not_modified:
            self.cache = response.content
        if self.cache is None:
            raise ValueError("HTTP getter cache is empty")
        return not_modified

    def _do_request(self) -> Response:
        """Gets the content from a http server via an uri"""
        domain = urlparse(self.url).netloc
        scheme = urlparse(self.url).scheme
        domain_uri = f"{scheme}://{domain}"
        if domain_uri not in self._credentials_registry:
            self._credentials_registry.update({domain_uri: self.credentials})
        creds = self._credentials_registry.get(domain_uri)
        session = creds.get_session() if creds else requests.Session()

        if self.etag:
            self._headers.update({"If-None-Match": self.etag})
        resp = session.get(url=self.url, timeout=5, allow_redirects=True, headers=self._headers)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as error:
            if not error.response.status_code == 401:
                raise error
            if os.environ.get(ENV_NAME_LOGPREP_CREDENTIALS_FILE):
                raise error
            raise CredentialsEnvNotFoundError(
                (
                    "Credentials file not found. Please set the environment variable "
                    f"'{ENV_NAME_LOGPREP_CREDENTIALS_FILE}'"
                )
            ) from error

        if "etag" in resp.headers:
            self.etag = resp.headers.get("etag")

        return resp

    @classmethod
    def refresh(cls):
        """Run all pending http getter schedulers"""
        for shared_target_data in cls._shared.values():
            if shared_target_data.scheduler:
                shared_target_data.scheduler.run_pending()


def refresh_getters():
    HttpGetter.refresh()
