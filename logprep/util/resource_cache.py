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

from attrs import define

from logprep.abc.exceptions import LogprepException
from logprep.abc.getter import Getter
from logprep.util.environ import ENV_VARS
from logprep.util.getter import GetterFactory, RefreshableGetter, RefreshableGetterError
from logprep.util.helper import DottedTemplate, JsonObject, get_dotted_field_value


class RetrievalContextError(LogprepException): ...


Uri: TypeAlias = str

RawUri: TypeAlias = Uri
ResolvedUri: TypeAlias = Uri
DynamicUriTemplate: TypeAlias = DottedTemplate


class ErrorContext(StrEnum):
    RESOLVE_URI = auto()
    RETRIEVE_URI = auto()
    HANDLE_CONTENT = auto()


@define(frozen=True, kw_only=True)
class CacheError:
    context: ErrorContext
    exception: Exception


T = TypeVar("T")


@define(frozen=True, kw_only=True)
class CacheItem(Generic[T]):
    raw_uri: RawUri
    resolved_uri: ResolvedUri | None = None
    content: T | None = None
    error: CacheError | None = None
    is_cached: bool = True
    is_dynamic: bool = False

    @property
    def value(self) -> T:
        if self.error:
            raise self.error.exception
        assert self.content is not None
        return self.content


class ResourceCache(Generic[T]):
    def __init__(
        self,
        tag: str,
        *,
        on_data: Callable[[Getter], T],
        on_update: Callable[[CacheItem[T]], None] | None = None,
        on_cleanup: Callable[[CacheItem[T]], None] | None = None,
        allow_dynamic_files: bool = False,
    ) -> None:
        self._tag = tag
        self._on_data = on_data
        self._on_update = on_update
        self._on_cleanup = on_cleanup
        self._resolve_cache: dict[RawUri, ResolvedUri | DynamicUriTemplate] = {}
        self._content_cache: dict[ResolvedUri, CacheItem[T]] = {}
        self._allow_dynamic_files = allow_dynamic_files

    def clear(self) -> None:
        RefreshableGetter.remove_callbacks_for_tag(self._tag)
        self._resolve_cache.clear()
        self._content_cache.clear()

    def clear_errors(self) -> None:
        to_delete = [uri for uri, item in self._content_cache.items() if item.error is not None]
        for uri in to_delete:
            self._cleanup_callback(uri)

    def get_error_items(self) -> Sequence[CacheItem[T]]:
        return [item for item in self._content_cache.values() if item.error is not None]

    def _getter_fetch_callback(self, getter: Getter, uri: ResolvedUri) -> None:
        new_item = self._get_updated_cache_item(getter, uri)
        self._content_cache[uri] = new_item

        if self._on_update is not None:
            self._on_update(new_item)

    def _get_updated_cache_item(self, getter: Getter, uri: ResolvedUri) -> CacheItem[T]:
        old_item = self._content_cache[uri]
        try:
            content = self._on_data(getter)
        except Exception as error:
            return CacheItem[T](
                raw_uri=old_item.raw_uri,
                resolved_uri=old_item.resolved_uri,
                error=CacheError(
                    context=ErrorContext.HANDLE_CONTENT,
                    exception=error,
                ),
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
        except Exception as exc:
            return CacheItem[T](
                raw_uri=raw_uri,
                resolved_uri=resolved_uri,
                error=CacheError(
                    context=ErrorContext.RETRIEVE_URI,
                    exception=exc,
                ),
                is_dynamic=is_dynamic,
                is_cached=is_cached,
            )
        if isinstance(getter, RefreshableGetter):
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

        error: CacheError | None = None
        content: T | None = None
        try:
            content = self._on_data(getter)
        except (RefreshableGetterError, FileNotFoundError) as exc:
            error = CacheError(
                context=ErrorContext.RETRIEVE_URI,
                exception=exc,
            )
        except Exception as exc:
            error = CacheError(
                context=ErrorContext.HANDLE_CONTENT,
                exception=exc,
            )
        return CacheItem[T](
            raw_uri=raw_uri,
            resolved_uri=resolved_uri,
            content=content,
            error=error,
            is_dynamic=is_dynamic,
            is_cached=is_cached,
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
        RefreshableGetter.keep_alive_for_target(resolved_uri)
        return self._content_cache[resolved_uri]

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
            identifier: get_dotted_field_value(event, identifier)
            for identifier in event_identifiers
        }

        for identifier, val in values.items():
            if val is None:
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
                is_dynamic=True,
            )

        self._resolve_cache[raw_uri] = uri_template
        return self._handle_dynamic_uri(raw_uri, uri_template, event)

    def get_value(self, uri: Uri, event: JsonObject | None = None) -> CacheItem[T]:
        cached_resolved = self._resolve_cache.get(uri)
        if cached_resolved is None:
            return self._handle_unknown_uri(uri, event)
        elif isinstance(cached_resolved, ResolvedUri):
            return self._handle_resolved_uri(uri, cached_resolved, is_dynamic=False)
        assert isinstance(cached_resolved, DynamicUriTemplate)
        return self._handle_dynamic_uri(uri, cached_resolved, event)
