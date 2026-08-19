"""Content getters provide a shared interface to get content from targets.
They are returned by the GetterFactory.
"""

import asyncio
import logging
import re
import ssl
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import cached_property
from importlib.metadata import version
from pathlib import Path
from string import Template
from typing import Any, ClassVar, Iterable, TypeAlias
from urllib.parse import urlparse

import aiohttp
from attrs import define, field, validators

from logprep.abc.exceptions import LogprepException
from logprep.ng.abc.getter import ContentType, Getter
from logprep.util.async_scheduler import AsyncScheduler
from logprep.util.credentials import (
    Credentials,
    CredentialsEnvNotFoundError,
    CredentialsFactory,
)
from logprep.util.defaults import (
    ENV_NAME_LOGPREP_CREDENTIALS_FILE,
    ENV_NAME_LOGPREP_GETTER_CONFIG,
)
from logprep.util.environ import ENV_VARS

logger = logging.getLogger("Getter")

rg_logger = logging.getLogger("RefreshableGetter")

AsyncCallback: TypeAlias = Callable[..., Awaitable[Any]]
CleanupCallback: TypeAlias = Callable[..., None]


class GetterNotFoundError(LogprepException):
    """Is raised if getter is not found"""

    def __init__(self, message) -> None:
        if message:
            super().__init__(message)


class RefreshableGetterError(LogprepException):
    """Is raised if refreshable getter could not update a value"""

    def __init__(self, message) -> None:
        if message:
            super().__init__(message)


class GetterFactory:
    """Provides methods to create getters"""

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
        target = cls._expand_variables(target, ENV_VARS)
        # get credentials
        if protocol is None:
            protocol = "file"
        if protocol == "file":
            return FileGetter(protocol=protocol, target=target)
        if protocol == "http" or protocol == "https":
            return HttpGetter(protocol=protocol, target=f"{protocol}://{target}")
        raise GetterNotFoundError(f"No getter for protocol '{protocol}'")

    @staticmethod
    def _expand_variables(posix_expr, context):
        env = defaultdict(lambda: "")
        env.update(context)
        return Template(posix_expr).substitute(env)

    @staticmethod
    def _dissect(getter_string: str) -> tuple[str, str]:
        regexp = r"^((?P<protocol>[^\s]+)://)?(?P<target>.+)"
        matches = re.match(regexp, getter_string)
        if matches is None:
            raise GetterNotFoundError(f"Could not parse '{getter_string}'")
        return matches.group("protocol"), matches.group("target")


@define(kw_only=True)
class DataSharedPerTarget:
    """Contains data that is shared for getters with the same target"""

    initialized: bool = False
    """Whether configuration-dependent state has been initialized"""

    target: str
    """The target for which this objects caches data"""

    cache: bytes | None = None
    """Value of the resource when it was last obtained"""

    content_type: ContentType | None = None
    """Content type of the resource when it was last obtained"""

    scheduler: AsyncScheduler | None = None
    """Scheduler used to trigger getter refreshes"""

    refresh_interval: int | None = None
    """Interval after which getters attempt to obtain the resource again"""

    timeout_interval: int | None = None
    """Amount of time after the last access, after which the cache will be invalidated"""

    default_return_value: bytes | None = None
    """Default value to be returned if defined in the configuration"""

    callbacks: list = field(factory=list)
    """Callbacks called after a resource has changed and was successfully obtained"""

    cleanup_callbacks: list = field(factory=list)
    """Callbacks called after a resource has timed out"""

    refreshing: bool = False
    """Used to check if getters are refreshing to prevent the scheduler running multiple times"""

    update_task: asyncio.Task[bool] | None = field(
        default=None,
        repr=False,
    )
    """Currently running cache update task"""

    hash: str | None = None
    """Hash value of the obtained resource"""

    last_called: float | None = None
    """Last called monotonic timestamp for timing out"""

    @property
    def timed_out(self) -> bool:
        """
        Whether the cached object has timed out,
        meaning :code:`timeout_interval` has passed since the last access
        """
        if self.timeout_interval is None:
            return False
        if self.last_called is None:
            return False
        return time.monotonic() - self.last_called > self.timeout_interval

    def keep_alive(self) -> None:
        """Signal a data access, rendering :code:`timeout_interval` to reset for this target"""
        rg_logger.debug("target signaled as still in use: %s", self.target)
        self.last_called = time.monotonic()


@define(kw_only=True)
class RefreshableGetter(Getter, ABC):
    """Interface for getters that refresh their value periodically"""

    _target_to_data_caches: ClassVar[dict[str, DataSharedPerTarget]] = {}
    """Dictionary to store DataSharedPerTarget objects per getter target"""

    def _init_scheduler(self) -> None:
        if self._refresh_interval < 0:
            raise ValueError(f"'refresh_interval' must be >= 0: {self._refresh_interval}")

        if self._timeout_interval < 0:
            raise ValueError(f"'timeout_interval' must be >= 0: {self._timeout_interval}")

        if self._refresh_interval > 0 and self.scheduler is None:
            self.scheduler = AsyncScheduler()
            self.scheduler.every(self._refresh_interval).seconds.do(self._refresh)  # type: ignore[attr-defined]

    @property
    def shared(self) -> DataSharedPerTarget:
        """Returns the shared data for current target"""
        if self.target not in self._target_to_data_caches:
            self.shared = DataSharedPerTarget(target=self.target)
        return self._target_to_data_caches[self.target]

    @shared.setter
    def shared(self, value: DataSharedPerTarget) -> None:
        """Set shared data for current target"""
        self._target_to_data_caches[self.target] = value

    @property
    def scheduler(self) -> AsyncScheduler | None:
        """Returns the scheduler for the current target"""
        return self.shared.scheduler

    @scheduler.setter
    def scheduler(self, value: AsyncScheduler) -> None:
        """Sets the scheduler for the target"""
        self.shared.scheduler = value

    @property
    def cache(self) -> bytes | None:
        """Returns the cache for the current target"""
        return self.shared.cache

    @cache.setter
    def cache(self, value: bytes) -> None:
        """Sets the cache for the current target"""
        self.shared.cache = value

    @property
    def content_type(self) -> ContentType | None:
        """Returns the content_type for the current target"""
        return self.shared.content_type

    @content_type.setter
    def content_type(self, value: ContentType | None) -> None:
        """Sets the content_type for the target"""
        self.shared.content_type = value

    @property
    def hash(self) -> str | None:
        """Returns the hash of the current targets value"""
        return self.shared.hash

    @hash.setter
    def hash(self, value: str) -> None:
        """Sets the hash of the current targets value"""
        self.shared.hash = value

    @cached_property
    def uri(self) -> str:
        """Returns the URI of the target"""
        # Protocol already in target
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", self.target):
            return self.target
        return f"{self.protocol}://{self.target}"

    @cached_property
    def legacy_target(self) -> str:
        """Return the legacy target which is the target stripped of https:// and http:// protocol prefixes"""
        return self.target.removeprefix("https://").removeprefix("http://")

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
        """Get the refresh interval for the current target"""

        interval = self.shared.refresh_interval

        if interval is None:
            raise RuntimeError("RefreshableGetter has not been initialized")

        return interval

    @_refresh_interval.setter
    def _refresh_interval(self, value: int) -> None:
        """Sets the refresh interval for the current target"""
        self.shared.refresh_interval = value

    @property
    def _timeout_interval(self) -> int:
        """Get the timeout interval for the current target"""
        interval = self.shared.timeout_interval

        if interval is None:
            raise RuntimeError("RefreshableGetter has not been initialized")

        return interval

    @_timeout_interval.setter
    def _timeout_interval(self, value: int) -> None:
        """Set the timeout interval for the current target"""
        self.shared.timeout_interval = value

    @property
    def _default_return_value(self) -> bytes | None:
        """Get the configured default return value"""
        if not self.shared.initialized:
            raise RuntimeError("RefreshableGetter has not been initialized")

        return self.shared.default_return_value

    @staticmethod
    def _build_callback(
        tag: str,
        fnc: Callable[..., Any],
        fnc_args: Iterable[Any] | None,
        fnc_kwargs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "tag": tag,
            "function": fnc,
            "args": fnc_args or [],
            "kwargs": fnc_kwargs or {},
        }

    @classmethod
    def _add_callback_to_shared(
        cls,
        shared: DataSharedPerTarget,
        callback_list_name: str,
        tag: str,
        fnc: Callable[..., Any],
        deduplication_key: tuple | None,
        fnc_args: Iterable[Any] | None,
        fnc_kwargs: dict[str, Any] | None,
    ) -> None:
        callbacks = getattr(shared, callback_list_name)
        callback = cls._build_callback(tag, fnc, fnc_args, fnc_kwargs)

        if deduplication_key is not None:
            if any(existing.get("key") == deduplication_key for existing in callbacks):
                return
            callback["key"] = deduplication_key

        callbacks.append(callback)

    def add_callback(
        self,
        tag: str,
        fnc: AsyncCallback,
        *,
        deduplication_key: tuple | None = None,
        fnc_args: Iterable[Any] | None = None,
        fnc_kwargs: dict[str, Any] | None = None,
    ):
        """Register a callback for successful refreshed data.

        If ``deduplication_key`` is set, an existing callback with the same key is kept
        and the new callback is ignored. The ``tag`` is used for later bulk removal and
        is independent from the deduplication key.
        """
        self._add_callback_to_shared(
            self.shared,
            "callbacks",
            tag,
            fnc,
            deduplication_key,
            fnc_args,
            fnc_kwargs,
        )

    @classmethod
    def add_callback_for_target(
        cls,
        target: str,
        tag: str,
        fnc: AsyncCallback,
        *,
        deduplication_key: tuple | None = None,
        fnc_args: Iterable[Any] | None = None,
        fnc_kwargs: dict[str, Any] | None = None,
    ):
        """Register a refresh callback for an already initialized target.

        This is a no-op if the target has no shared getter state. ``deduplication_key``
        prevents duplicate callback registration without affecting tag-based removal.
        """
        shared = cls._target_to_data_caches.get(target)
        if shared is None:
            return

        cls._add_callback_to_shared(
            shared,
            "callbacks",
            tag,
            fnc,
            deduplication_key,
            fnc_args,
            fnc_kwargs,
        )

    def add_cleanup_callback(
        self,
        tag: str,
        fnc: CleanupCallback,
        *,
        deduplication_key: tuple | None = None,
        fnc_args: Iterable[Any] | None = None,
        fnc_kwargs: dict[str, Any] | None = None,
    ):
        """Register a callback that runs when the target times out and is removed.

        If ``deduplication_key`` is set, an existing cleanup callback with the same key
        is kept and the new callback is ignored.
        """
        self._add_callback_to_shared(
            self.shared,
            "cleanup_callbacks",
            tag,
            fnc,
            deduplication_key,
            fnc_args,
            fnc_kwargs,
        )

    async def _ensure_initialized(self) -> None:
        """Initialize configuration-dependent shared getter state once"""
        if self.shared.initialized:
            return

        config = await self._get_getter_config_entry()

        refresh_interval = config.get("refresh_interval", 0)
        timeout_interval = config.get("timeout_interval", 60)

        if refresh_interval < 0:
            raise ValueError(f"'refresh_interval' must be >= 0: {refresh_interval}")

        if timeout_interval < 0:
            raise ValueError(f"'timeout_interval' must be >= 0: {timeout_interval}")

        self.shared.refresh_interval = refresh_interval
        self.shared.timeout_interval = timeout_interval

        default_return_value = config.get("default_return_value")
        self.shared.default_return_value = (
            default_return_value.encode("utf-8") if default_return_value is not None else None
        )

        self._init_scheduler()
        self.shared.initialized = True

    async def _get_getter_config_entry(self) -> dict:
        if ENV_NAME_LOGPREP_GETTER_CONFIG not in ENV_VARS:
            return {}

        getter_file_path = ENV_VARS.get(ENV_NAME_LOGPREP_GETTER_CONFIG)
        if not getter_file_path or getter_file_path == self.target and self.protocol == "file":
            return {}

        getter = FileGetter(protocol="file", target=getter_file_path)
        getters_config = await getter.get_dict()

        for candidate in (self.uri, self.target, self.legacy_target):
            if candidate in getters_config:
                return getters_config[candidate]

        for configured_target, config in getters_config.items():
            if self._target_matches(configured_target):
                return config

        return {}

    def _target_matches(self, configured_target: str) -> bool:
        candidates = (self.uri, self.legacy_target)

        if configured_target.endswith("*"):
            prefix = configured_target[:-1]
            return any(candidate.startswith(prefix) for candidate in candidates)

        return configured_target in candidates

    async def _refresh(self) -> None:
        """Refresh the current HTTP getter"""
        await self._ensure_initialized()

        if self.shared.refreshing:
            return

        self.shared.refreshing = True

        try:
            try:
                was_modified = await self._update_cache()
            except RefreshableGetterError as error:
                self._log_cache_warning(error)
                was_modified = False

            if not was_modified:
                rg_logger.debug(
                    "target has not been modified, cache is up-to-date: %s",
                    self.target,
                )
                return

            rg_logger.debug(
                "target was modified, cache updated and running callbacks: %s",
                self.target,
            )

            for callback in self._callbacks:
                try:
                    await callback["function"](
                        *callback["args"],
                        **callback["kwargs"],
                    )
                except Exception:  # pylint: disable=broad-except
                    rg_logger.exception(
                        "refresh callback failed for target '%s' with tag '%s'",
                        self.target,
                        callback["tag"],
                    )
        finally:
            self.shared.refreshing = False

    async def _update_cache(self) -> bool:
        """Update the cache while sharing concurrent updates for the same target"""
        if self.shared.update_task is None:
            self.shared.update_task = asyncio.create_task(self._update_cache_once())

        update_task = self.shared.update_task

        try:
            return await asyncio.shield(update_task)
        finally:
            if update_task.done() and self.shared.update_task is update_task:
                self.shared.update_task = None

    async def _update_cache_once(self) -> bool:
        """Update the cache of the current http getter"""
        content, content_type, was_modified = await self._get_from_target()

        if was_modified and content is not None:
            self.content_type = content_type
            self.cache = content

        if self.cache is None:
            raise ValueError(f"{type(self).__name__} cache is empty")

        return was_modified

    @abstractmethod
    async def _get_from_target(
        self,
    ) -> tuple[bytes | None, ContentType | None, bool]:
        """Get value from target and return if it changed or not since it was last obtained"""

    def _handle_cache_error(self, error: RefreshableGetterError | ValueError):
        """Return default value if it was configured else raise error"""
        if self._default_return_value is None:
            raise error

        self.content_type = None
        self.cache = self._default_return_value

    def _log_cache_warning(self, error: Exception):
        rg_logger.warning(
            f"Not updating {type(self).__name__} cache with URI '{self.uri}' due to: %s", error
        )

    async def _get_raw(self) -> tuple[bytes, ContentType | None]:
        """Gets the content from cache and update cache if needed"""

        await self._ensure_initialized()

        if self.shared.refreshing and self.cache is not None:
            return self.cache, self.content_type

        if self._refresh_interval > 0 and self.scheduler:
            await self.scheduler.run_pending()

            if self.cache is None:
                try:
                    await self._update_cache()
                except RefreshableGetterError as error:
                    self._handle_cache_error(error)
                    self._log_cache_warning(error)
        else:
            try:
                await self._update_cache()
            except RefreshableGetterError as error:
                if self.cache is None:
                    self._handle_cache_error(error)

                self._log_cache_warning(error)

        if self.cache is None:
            raise ValueError(f"Cache is empty for {type(self).__name__} with URI '{self.uri}'")

        return self.cache, self.content_type

    def keep_alive(self):
        """Signal a data access, rendering :code:`timeout_interval` to reset for this target"""
        self.shared.keep_alive()

    def timed_out(self) -> bool:
        """Whether this target has timed out"""
        return self.shared.timed_out

    @classmethod
    def timed_out_for_target(cls, target: str) -> bool:
        """Whether the target has timed out"""
        target_shared = cls._target_to_data_caches.get(target)
        if target_shared is None:
            return False

        return target_shared.timed_out

    @classmethod
    def remove_callbacks_for_tag(cls, tag: str) -> None:
        """Removes update and cleanup callbacks for the given tag"""
        empty_targets = []

        for target, shared in cls._target_to_data_caches.items():
            shared.callbacks = [
                callback for callback in shared.callbacks if callback.get("tag") != tag
            ]
            shared.cleanup_callbacks = [
                callback for callback in shared.cleanup_callbacks if callback.get("tag") != tag
            ]

            if shared.cache is None and not shared.callbacks and not shared.cleanup_callbacks:
                empty_targets.append(target)

        for target in empty_targets:
            cls._target_to_data_caches.pop(target, None)

    @classmethod
    def keep_alive_for_target(cls, target: str):
        """Signal a data access, rendering :code:`timeout_interval` to reset for this target"""

        shared = cls._target_to_data_caches.get(target)
        if shared is None:
            rg_logger.warning("attempted to keep alive an already deleted target: %s", target)
            return

        shared.keep_alive()

    @classmethod
    async def refresh(cls) -> None:
        """Run pending refresh schedulers and clean up timed-out targets"""
        for target, shared_target_data in list(cls._target_to_data_caches.items()):
            if cls.timed_out_for_target(target):
                rg_logger.debug("target has timed out and will be cleaned up: %s", target)
                del cls._target_to_data_caches[target]

                for callback in shared_target_data.cleanup_callbacks:
                    callback["function"](*callback["args"], **callback["kwargs"])

                continue

            if shared_target_data.scheduler:
                await shared_target_data.scheduler.run_pending()

    @classmethod
    def reset(cls, cleanup: bool = False):
        """Wipe the cache and optionally run cleanup callbacks"""
        for target, shared_target_data in list(cls._target_to_data_caches.items()):
            del cls._target_to_data_caches[target]
            if cleanup:
                for callback in shared_target_data.cleanup_callbacks:
                    callback["function"](*callback["args"], **callback["kwargs"])


@define(kw_only=True)
class FileGetter(Getter):
    """Get files (and only files) from a filesystem.

    Matching string examples:

    * :code:`/yourpath/yourfile.extension`
    * :code:`file://yourpath/yourfile.extension`
    """

    async def _get_raw(self) -> tuple[bytes, ContentType | None]:
        """Open file and return its binary content and detected content type"""
        path = Path(self.target)
        raw_content = await asyncio.to_thread(path.read_bytes)

        match path.suffix:
            case ".txt":
                return raw_content, "text/plain"
            case ".json":
                return raw_content, "application/json"
            case ".yml":
                return raw_content, "application/yaml"
            case _:
                return raw_content, None


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

    # Intentionally shared across HttpGetter instances to reuse credentials per domain.
    _credentials_registry: ClassVar[dict[str, Credentials]] = {}  # shared
    _MAX_RETRIES: ClassVar[int] = 3
    _RETRY_STATUS_CODES: ClassVar[frozenset[int]] = frozenset({500, 502, 503, 504})

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

    @property
    def credentials(self) -> Credentials:
        """Get credentials for target from environment variable"""
        creds = None
        if ENV_NAME_LOGPREP_CREDENTIALS_FILE in ENV_VARS:
            creds = CredentialsFactory.from_target(self.uri)
        return creds if creds else Credentials()

    async def _get_aiohttp_request_kwargs(self) -> dict[str, Any]:
        """Build aiohttp request arguments from the configured credentials"""
        return await asyncio.to_thread(self._get_aiohttp_request_kwargs_sync)

    @staticmethod
    def _create_ssl_context(
        verify: bool | str,
        cert: str | tuple[str, str] | None,
    ) -> ssl.SSLContext | bool | None:
        """Convert credential TLS settings to aiohttp SSL settings"""
        if verify is True and cert is None:
            return None

        if verify is False and cert is None:
            return False

        if isinstance(verify, str):
            ssl_context = ssl.create_default_context(cafile=verify)
        else:
            ssl_context = ssl.create_default_context()

        if verify is False:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        if cert:
            if isinstance(cert, tuple):
                cert_file, key_file = cert
                ssl_context.load_cert_chain(
                    certfile=cert_file,
                    keyfile=key_file,
                )
            else:
                ssl_context.load_cert_chain(certfile=cert)

        return ssl_context

    def _get_aiohttp_request_kwargs_sync(self) -> dict[str, Any]:
        """Build aiohttp request arguments from the configured credentials"""
        domain = urlparse(self.uri).netloc
        scheme = urlparse(self.uri).scheme
        domain_uri = f"{scheme}://{domain}"

        if domain_uri not in self._credentials_registry:
            self._credentials_registry[domain_uri] = self.credentials

        credentials = self._credentials_registry[domain_uri]
        session = credentials.get_session()

        request_kwargs: dict[str, Any] = {}
        headers = {}

        if session.auth:
            username, password = session.auth
            headers["Authorization"] = aiohttp.encode_basic_auth(
                username,
                password,
            )

        authorization = session.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization

        if headers:
            request_kwargs["headers"] = headers

        ssl_context = self._create_ssl_context(
            verify=session.verify,
            cert=session.cert,
        )
        if ssl_context is not None:
            request_kwargs["ssl"] = ssl_context

        return request_kwargs

    async def _get_from_target(
        self,
    ) -> tuple[bytes | None, ContentType | None, bool]:
        content, content_type, status = await self._do_request()
        return content, content_type, status != 304

    async def _do_request(
        self,
    ) -> tuple[bytes, ContentType | None, int]:
        """Gets the content from a http server via a URI"""
        request_kwargs = await self._get_aiohttp_request_kwargs()

        credential_headers = request_kwargs.pop("headers", {})
        headers = credential_headers | self._headers

        if self.hash:
            headers["If-None-Match"] = self.hash

        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(self._MAX_RETRIES + 1):
                    try:
                        async with session.get(
                            url=self.uri,
                            timeout=aiohttp.ClientTimeout(total=5),
                            allow_redirects=True,
                            headers=headers,
                            **request_kwargs,
                        ) as response:
                            if (
                                response.status in self._RETRY_STATUS_CODES
                                and attempt < self._MAX_RETRIES
                            ):
                                logger.warning(
                                    "retrying %s after status=%d (%d/%d)",
                                    self.uri,
                                    response.status,
                                    attempt + 1,
                                    self._MAX_RETRIES,
                                )
                                continue

                            if response.status == 401:
                                if ENV_VARS.get(ENV_NAME_LOGPREP_CREDENTIALS_FILE):
                                    raise RefreshableGetterError(
                                        f"{response.status}, "
                                        f"message={response.reason!r}, "
                                        f"url={self.uri!r}"
                                    )

                                raise CredentialsEnvNotFoundError(
                                    "Credentials file not found. Please set the environment variable "
                                    f"'{ENV_NAME_LOGPREP_CREDENTIALS_FILE}'"
                                )

                            response.raise_for_status()

                            logger.debug(
                                "querying %s with etag=%s yielded status=%d",
                                self.uri,
                                self.hash,
                                response.status,
                            )

                            if "ETag" in response.headers:
                                self.hash = response.headers["ETag"]

                            return (
                                await response.read(),
                                response.content_type,
                                response.status,
                            )

                    except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                        if attempt >= self._MAX_RETRIES:
                            raise

                        logger.warning(
                            "retrying %s after connection error (%d/%d)",
                            self.uri,
                            attempt + 1,
                            self._MAX_RETRIES,
                        )

        except aiohttp.ClientError as error:
            raise RefreshableGetterError(str(error)) from error
        except asyncio.TimeoutError as error:
            raise RefreshableGetterError(str(error)) from error

        raise RuntimeError("HTTP request retry loop exited unexpectedly")


async def refresh_getters():
    """Refreshes all refreshable getters"""
    await RefreshableGetter.refresh()
