"""The resource cache provides an interface to work with contents derived from
resources. It supports static and event-dynamic handling of resources and
implements caching and reloading (via the getter system).
"""

from enum import StrEnum, auto
from typing import (
    Callable,
    Generic,
    Sequence,
    TypeAlias,
    TypeVar,
)
from uuid import uuid4

from attrs import define

from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter
from logprep.factory_error import InvalidResourcesError
from logprep.util.environ import ENV_VARS
from logprep.util.getter import (
    GetterFactory,
    GetterNotFoundError,
    RefreshableGetter,
    RefreshableGetterError,
)
from logprep.util.helper import (
    MISSING,
    DottedTemplate,
    JsonObject,
    get_dotted_field_value_with_missing,
)


class RetrievalContextError(LogprepException):
    """Exception indicating insufficient context on resource retrieval"""


Uri: TypeAlias = str

RawUri: TypeAlias = Uri
ResolvedUri: TypeAlias = Uri
DynamicUriTemplate: TypeAlias = DottedTemplate


class ErrorContext(StrEnum):
    """The context an error occurred in"""

    RESOLVE_URI = auto()
    """An error occurred while resolving the uri"""

    RETRIEVE_URI = auto()
    """An error occurred while retrieving the resolved uri"""

    HANDLE_CONTENT = auto()
    """An error occurred while processing the retrieved content"""


@define(frozen=True, kw_only=True)
class CacheError:
    """Information about the error state of an CacheItem in a ResourceCache context"""

    context: ErrorContext
    """The context the error occurred in"""

    exception: Exception
    """The actual exception caught"""


T = TypeVar("T")


@define(frozen=True, kw_only=True)
class CacheItem(Generic[T]):
    """Caching information for a requests handled by the ResourceCache"""

    raw_uri: RawUri
    """The URI originally passed to the cache"""

    resolved_uri: ResolvedUri | None = None
    """The URI with resolved templating used for resource retrieval"""

    content: T | None = None
    """The content derived from the retrieved resource"""

    error: CacheError | None = None
    """Information about a possible errors related to the item"""

    is_cached: bool = True
    """True if this item is cached in the ResourceCache"""

    will_refresh: bool = False
    """True if the resource is subject of the automatic refresh loop"""

    is_dynamic: bool = False
    """True if the CacheItem originates from a event-dynamic request"""

    @property
    def has_unrecoverable_error(self) -> bool:
        """True if the cache item has an error and is unrecoverable"""
        return self.error is not None and not (self.is_dynamic or self.will_refresh)


class ResourceCache(Generic[T]):
    """An caching system to work with contents derived from resources.
    Taking care of refresh/timeout lifecycle by utilizing the Getter system"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        on_data: Callable[[Getter], T],
        on_update: Callable[[CacheItem[T]], None] | None = None,
        on_cleanup: Callable[[CacheItem[T]], None] | None = None,
        allow_dynamic_files: bool = False,
    ) -> None:
        """
        Initialize a new ResourceCache object.

        Parameters
        ----------
        on_data : Callable[[Getter], T]
            Callback called on initially retrieving and updating resources.
            Responsible for deriving the target type form the resource.
        on_update : Callable[[CacheItem[T]], None] | None, optional
            Callback invoked if any CacheItem changes for any reason.
        on_cleanup : Callable[[CacheItem[T]], None] | None, optional
            Callback invoked if a CacheItem reaches the end of its lifecycle
        allow_dynamic_files : bool, optional
            If set to True a url templating will be enabled on URIs referencing
            Files. Defaults to False.
        """
        self._tag = f"{type(self).__name__}-{uuid4()}"
        self._on_data = on_data
        self._on_update = on_update
        self._on_cleanup = on_cleanup
        self._resolve_cache: dict[RawUri, ResolvedUri | DynamicUriTemplate] = {}
        self._content_cache: dict[ResolvedUri, CacheItem[T]] = {}
        self._allow_dynamic_files = allow_dynamic_files

    def clear(self) -> None:
        """Clear the contents of this ResourceCache"""
        RefreshableGetter.remove_callbacks_for_tag(self._tag)
        self._resolve_cache.clear()
        self._content_cache.clear()

    def clear_errors(self) -> None:
        """Clear all cached items currently in error state"""
        to_delete = [uri for uri, item in self._content_cache.items() if item.error is not None]
        for uri in to_delete:
            self._cleanup_callback(uri)

    def get_error_items(self) -> Sequence[CacheItem[T]]:
        """Get all cached items currently in error state"""
        return [item for item in self._content_cache.values() if item.error is not None]

    def get_static_resource_error_state(self) -> InvalidResourcesError | None:
        """Returns a InvalidResourcesError if there are any errors with on static
        Resources. If no errors are present None is returned."""

        static_errors = {
            item.raw_uri: item.error.exception
            for item in self._content_cache.values()
            if item.error is not None and not item.is_dynamic
        }
        if len(static_errors) == 0:
            return None
        return InvalidResourcesError(static_errors)

    def _getter_fetch_callback(self, getter: Getter, uri: ResolvedUri) -> None:
        new_item = self._get_updated_cache_item(getter, uri)
        self._content_cache[uri] = new_item

        if self._on_update is not None:
            self._on_update(new_item)

    def _get_updated_cache_item(self, getter: Getter, uri: ResolvedUri) -> CacheItem[T]:
        old_item = self._content_cache[uri]
        try:
            content = self._on_data(getter)
        except Exception as error:  # pylint: disable=broad-exception-caught
            return CacheItem[T](
                raw_uri=old_item.raw_uri,
                resolved_uri=old_item.resolved_uri,
                error=CacheError(
                    context=ErrorContext.HANDLE_CONTENT,
                    exception=error,
                ),
                will_refresh=old_item.will_refresh,
                is_dynamic=old_item.is_dynamic,
            )

        return CacheItem[T](
            raw_uri=old_item.raw_uri,
            resolved_uri=old_item.resolved_uri,
            content=content,
            is_dynamic=old_item.is_dynamic,
        )

    def _cleanup_callback(self, uri: ResolvedUri) -> None:
        assert uri in self._content_cache
        old_item = self._content_cache[uri]
        if old_item is None:
            return
        del self._content_cache[uri]
        if self._on_cleanup:
            self._on_cleanup(old_item)

    def _create_cache_item(
        self, raw_uri: RawUri, resolved_uri: ResolvedUri, is_dynamic: bool, is_cached: bool
    ) -> CacheItem[T]:
        try:
            getter = GetterFactory.from_string(resolved_uri, expand_env=False)
        except GetterNotFoundError as exc:
            return CacheItem[T](
                raw_uri=raw_uri,
                resolved_uri=resolved_uri,
                error=CacheError(
                    context=ErrorContext.RESOLVE_URI,
                    exception=exc,
                ),
                is_dynamic=is_dynamic,
                is_cached=is_cached,
                will_refresh=False,
            )

        error: CacheError | None = None
        content: T | None = None
        is_refreshable = False
        try:
            content = self._on_data(getter)
        except (RefreshableGetterError, FileNotFoundError) as exc:
            error = CacheError(
                context=ErrorContext.RETRIEVE_URI,
                exception=exc,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            error = CacheError(
                context=ErrorContext.HANDLE_CONTENT,
                exception=exc,
            )

        if isinstance(getter, RefreshableGetter):
            is_refreshable = True
            if is_dynamic:
                # NOTE: keep_alive_for_target must not be called for static resources.
                RefreshableGetter.keep_alive_for_target(resolved_uri)
            getter.keep_alive()
            key = (self._tag, resolved_uri)
            getter.add_callback(
                self._tag,
                self._getter_fetch_callback,
                deduplication_key=key,
                fnc_args=[getter, resolved_uri],
            )
            getter.add_cleanup_callback(
                self._tag,
                self._cleanup_callback,
                deduplication_key=key,
                fnc_args=[resolved_uri],
            )

        return CacheItem[T](
            raw_uri=raw_uri,
            resolved_uri=resolved_uri,
            content=content,
            error=error,
            is_dynamic=is_dynamic,
            is_cached=is_cached,
            will_refresh=is_refreshable,
        )

    def _handle_resolved_uri(
        self, raw_uri: RawUri, resolved_uri: ResolvedUri, is_dynamic: bool
    ) -> CacheItem:
        if resolved_uri not in self._content_cache:
            new_item = self._create_cache_item(
                raw_uri, resolved_uri, is_dynamic=is_dynamic, is_cached=True
            )
            self._content_cache[resolved_uri] = new_item
            if self._on_update is not None:
                self._on_update(new_item)
        cache_item = self._content_cache[resolved_uri]
        if cache_item.is_dynamic and cache_item.will_refresh:
            # NOTE: keep_alive_for_target must not be called for static resources.
            RefreshableGetter.keep_alive_for_target(resolved_uri)
        return cache_item

    def _handle_dynamic_uri(
        self, raw_uri: RawUri, uri_template: DynamicUriTemplate, event: JsonObject | None
    ) -> CacheItem[T]:
        event_identifiers = uri_template.get_identifiers()

        def _resolve_error(exception: Exception) -> CacheItem[T]:
            return CacheItem[T](
                raw_uri=raw_uri,
                error=CacheError(context=ErrorContext.RESOLVE_URI, exception=exception),
                is_cached=False,
                is_dynamic=True,
            )

        if event is None:
            return _resolve_error(
                RetrievalContextError("Trying to access event-dynamic resource outside of event")
            )

        values = {
            identifier: get_dotted_field_value_with_missing(event, identifier)
            for identifier in event_identifiers
        }

        for identifier, val in values.items():
            if val is MISSING:
                return _resolve_error(
                    ValueError(f"missing event field {identifier!r} for dynamic URI")
                )

            if not isinstance(val, (str, int)):
                return _resolve_error(
                    ValueError(f"value for dynamic URI field {identifier!r} is not a scalar value")
                )

        resolved_uri = uri_template.substitute(values)

        return self._handle_resolved_uri(raw_uri, resolved_uri, is_dynamic=True)

    def _handle_unknown_uri(self, raw_uri: RawUri, event: JsonObject | None) -> CacheItem[T]:
        resolved_uri = DottedTemplate(raw_uri).safe_substitute(ENV_VARS)
        uri_template = DottedTemplate(resolved_uri)
        if len(uri_template.get_identifiers()) == 0:
            self._resolve_cache[raw_uri] = resolved_uri

            return self._handle_resolved_uri(raw_uri, resolved_uri, is_dynamic=False)

        if not self._allow_dynamic_files and not resolved_uri.startswith("http"):
            return CacheItem[T](
                raw_uri=raw_uri,
                error=CacheError(
                    context=ErrorContext.RESOLVE_URI,
                    exception=RetrievalContextError(
                        "Dynamic file URIs are not supported",
                    ),
                ),
                is_cached=False,
                is_dynamic=False,
            )

        self._resolve_cache[raw_uri] = uri_template
        return self._handle_dynamic_uri(raw_uri, uri_template, event)

    def get_cache_item(self, uri: Uri, event: JsonObject | None = None) -> CacheItem[T]:
        """Retrieve a CacheItem from the passed uri and optional event data
        for event-dynamic resources.
        The function will never raise but communicate any errors via the returned CacheItem.
        """
        cached_resolved = self._resolve_cache.get(uri)
        if cached_resolved is None:
            return self._handle_unknown_uri(uri, event)
        if isinstance(cached_resolved, ResolvedUri):
            return self._handle_resolved_uri(uri, cached_resolved, is_dynamic=False)
        assert isinstance(cached_resolved, DynamicUriTemplate)
        return self._handle_dynamic_uri(uri, cached_resolved, event)

    def get_value(self, uri: Uri, event: JsonObject | None = None) -> T:
        """Get the value derived from the passed uri and event data
        for event-dynamic resources.
        The function will raise if an exception is associated with the CacheItem
        associated to the resource.
        """
        cache_item = self.get_cache_item(uri, event)
        if cache_item.error is not None:
            raise cache_item.error.exception
        assert cache_item.content is not None
        return cache_item.content

    def preload(self, *uris: Uri) -> None:
        """Attempts to load all passed URIs. Raises an InvalidResourcesError
        if an uri is non-dynamic and not refreshable"""
        results = [self.get_cache_item(uri) for uri in uris]
        unrecoverable_errors = {
            item.raw_uri: item.error.exception
            for item in results
            if item.error is not None and item.has_unrecoverable_error
        }
        if len(unrecoverable_errors) > 0:
            raise InvalidResourcesError(unrecoverable_errors)
