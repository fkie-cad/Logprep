"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from functools import cached_property
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
from logprep.abc.getter import Getter
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


class RefreshableGetterError(LogprepException):
    """Is raised if refreshable getter could not update a value."""

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
class DataSharedPerTarget:
    """Contains data that is shared for getters with the same target"""

    cache: bytes | None = None
    """Value of the resource when it was last obtained"""

    scheduler: Scheduler | None = None
    """Scheduler used to trigger getter refreshes"""

    refresh_interval: int | None = None
    """Interval after which getters attempt to obtain the resource again"""

    default_return_value: bytes | None = None
    """Default value to be returned if defined in the configuration"""

    callbacks: list = []
    """Callbacks called after a resource has changed and was successfully obtained"""

    refreshing: bool = False
    """Used to check if getters are refreshing to prevent the scheduler running multiple times"""

    hash: str | None = None
    """Hash value of the obtained resource"""


@define(kw_only=True)
class RefreshableGetter(Getter, ABC):
    """Interface for getters that refresh their value periodically"""

    _logger = logging.getLogger("RefreshableGetter")

    _shared: ClassVar[dict[str, DataSharedPerTarget]] = {}
    """Dictionary to store DataSharedPerTarget objects per getter target"""

    def _init_scheduler(self):
        if self._refresh_interval < 0:
            raise ValueError(f"'refresh_interval' must be >= 0: {self._refresh_interval}")
        if self._refresh_interval > 0:
            if self.scheduler is None:
                self.scheduler = Scheduler()
                self.scheduler.every(self._refresh_interval).seconds.do(self._refresh)

    @property
    def shared(self) -> DataSharedPerTarget:
        """Returns the shared data for current target"""
        if self.target not in self._shared:
            self.shared = DataSharedPerTarget()
        return self._shared[self.target]

    @shared.setter
    def shared(self, value: DataSharedPerTarget) -> None:
        """Set shared data for current target"""
        self._shared[self.target] = value

    @property
    def scheduler(self) -> Scheduler:
        """Returns the scheduler for the current target"""
        return self.shared.scheduler

    @scheduler.setter
    def scheduler(self, value: Scheduler) -> None:
        """sets the scheduler for the target"""
        self.shared.scheduler = value

    @property
    def cache(self) -> bytes | None:
        """Returns the cache for the current target"""
        return self.shared.cache

    @cache.setter
    def cache(self, value: bytes) -> None:
        """Sets the cache for the current targe"""
        self.shared.cache = value

    @property
    def hash(self) -> str | None:
        """Returns the hash of the current targets value"""
        return self.shared.hash

    @hash.setter
    def hash(self, value: str) -> None:
        """Sets the hash of the current targets value"""
        self.shared.hash = value

    @property
    def uri(self) -> str:
        """Returns the URI of the target"""
        return f"{self.protocol}://{self.target}"

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

    @cached_property
    def _default_return_value(self) -> bytes | None:
        """Configured default value to be returned if no value could be retrieved"""
        if self.shared.default_return_value is None:
            self.shared.default_return_value = self._get_default_return_value()
        return self.shared.default_return_value

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
            if getter_file_path == self.target and self.protocol == "file":
                return 0
            getters_config = FileGetter(protocol="file", target=getter_file_path).get_dict()  # type: ignore
            return getters_config.get(self.target, {}).get("refresh_interval", 0)
        return 0

    def _get_default_return_value(self) -> bytes | None:
        """Get default return value from a configuration file"""
        if ENV_NAME_LOGPREP_GETTER_CONFIG in os.environ:
            getter_file_path = os.environ.get(ENV_NAME_LOGPREP_GETTER_CONFIG)
            if getter_file_path == self.target and self.protocol == "file":
                return None
            getters_config = FileGetter(protocol="file", target=getter_file_path).get_dict()  # type: ignore
            default_return_value = getters_config.get(self.target, {}).get("default_return_value")
            if default_return_value is None:
                return None
            return default_return_value.encode("utf-8")
        return None

    def _refresh(self) -> None:
        """Refresh the current http getter"""
        if self.shared.refreshing:
            return
        self.shared.refreshing = True
        try:
            was_modified = self._update_cache()
        except RefreshableGetterError as error:
            self._log_cache_warning(error)
            was_modified = False
        if not was_modified:
            self.shared.refreshing = False
            return
        for callback in self._callbacks:
            callback["function"](*callback["args"], **callback["kwargs"])
        self.shared.refreshing = False

    def _update_cache(self) -> bool:
        """Update the cache of the current http getter"""
        content, was_modified = self._get_from_target()
        if was_modified and content is not None:
            self.cache = content
        if self.cache is None:
            raise ValueError(f"{type(self).__name__} cache is empty")
        return was_modified

    @abstractmethod
    def _get_from_target(self) -> tuple[bytes | None, bool]:
        """Get value from target and return if it changed or not since it was last obtained"""

    def _handle_cache_error(self, error: RefreshableGetterError | ValueError):
        """Return default value if it was configured else raise error"""
        if self._default_return_value is None:
            raise error
        self.cache = self._default_return_value

    def _log_cache_warning(self, error: Exception):
        self._logger.warning(
            f"Not updating {type(self).__name__} cache with URI '{self.uri}' due to: %s", error
        )

    def get_raw(self) -> bytes:
        """Gets the content from cache and update cache if needed"""
        if self._refresh_interval > 0 and self.scheduler:
            self.scheduler.run_pending()
            if self.cache is None:
                try:
                    self._update_cache()
                except RefreshableGetterError as error:
                    self._handle_cache_error(error)
                    self._log_cache_warning(error)
        else:
            try:
                self._update_cache()
            except RefreshableGetterError as error:
                if self.cache is None:
                    self._handle_cache_error(error)
                self._log_cache_warning(error)
        if self.cache is None:
            raise ValueError(f"Cache is empty for {type(self).__name__} with URI '{self.uri}'")
        return self.cache

    @classmethod
    def refresh(cls):
        """Run all pending getter schedulers"""
        for shared_target_data in cls._shared.values():
            if shared_target_data.scheduler:
                shared_target_data.scheduler.run_pending()


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
class HttpGetter(RefreshableGetter):
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

        self._init_scheduler()

    @property
    def credentials(self) -> Credentials:
        """Get credentials for target from environment variable"""
        creds = None
        if ENV_NAME_LOGPREP_CREDENTIALS_FILE in os.environ:
            creds = CredentialsFactory.from_target(self.uri)
        return creds if creds else Credentials()

    def _get_from_target(self) -> tuple[bytes | None, bool]:
        response = self._do_request()
        was_modified = response.status_code != 304
        return response.content, was_modified

    def _do_request(self) -> Response:
        """Gets the content from a http server via a URI"""
        if self.hash:
            self._headers.update({"If-None-Match": self.hash})
        try:
            session = self._get_requests_session()
            resp = session.get(url=self.uri, timeout=5, allow_redirects=True, headers=self._headers)
        except requests.exceptions.RequestException as error:
            raise RefreshableGetterError(str(error)) from error
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as error:
            self._handle_http_error(error)
        if "etag" in resp.headers:
            self.hash = resp.headers.get("etag")
        return resp

    def _get_requests_session(self) -> requests.Session:
        domain = urlparse(self.uri).netloc
        scheme = urlparse(self.uri).scheme
        domain_uri = f"{scheme}://{domain}"
        if domain_uri not in self._credentials_registry:
            self._credentials_registry.update({domain_uri: self.credentials})
        creds = self._credentials_registry.get(domain_uri)
        session = creds.get_session() if creds else requests.Session()
        return session

    @staticmethod
    def _handle_http_error(error: requests.exceptions.HTTPError):
        if not error.response.status_code == 401:
            raise RefreshableGetterError(str(error)) from error
        if os.environ.get(ENV_NAME_LOGPREP_CREDENTIALS_FILE):
            raise RefreshableGetterError(str(error)) from error
        raise CredentialsEnvNotFoundError(
            (
                "Credentials file not found. Please set the environment variable "
                f"'{ENV_NAME_LOGPREP_CREDENTIALS_FILE}'"
            )
        ) from error


def refresh_getters():
    """Refreshes all refreshable getters"""
    RefreshableGetter.refresh()
