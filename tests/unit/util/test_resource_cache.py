# pylint: disable=missing-docstring
# pylint: disable=assignment-from-none
from unittest.mock import Mock
from uuid import uuid4

import pytest
import responses

from logprep.abc.getter import Getter
from logprep.util.getter import RefreshableGetterError
from logprep.util.resource_cache import (
    ErrorContext,
    ResourceCache,
    RetrievalContextError,
)
from tests.conftest import mock_env


class TestResourceCache:

    @responses.activate
    def test_get_resource_simple_happy_path(self):

        resource_content = str(uuid4())

        def data_callback(getter: Getter):
            return str(getter.get_raw(), encoding="utf-8")

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, uri, body=resource_content)

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result = cache.get_value(uri)

        assert endpoint.call_count == 1
        assert result.content == resource_content
        assert result.raw_uri == uri
        assert result.resolved_uri == uri
        assert result.error is None
        assert result.is_cached is True
        assert result.is_dynamic is False
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_idempotent_trough_caching(self):

        resource_content = str(uuid4())

        def data_callback(getter: Getter):
            return str(getter.get_raw(), encoding="utf-8")

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, uri, body=resource_content)

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result1 = cache.get_value(uri)
        result2 = cache.get_value(uri)

        assert endpoint.call_count == 1
        assert id(result1) == id(result2)
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_resolved_from_env(self):

        resource_content = str(uuid4())

        def data_callback(getter: Getter):
            return str(getter.get_raw(), encoding="utf-8")

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        raw_uri = "https://example.dd/${MY_ENV}"
        resolved_uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, resolved_uri, body=resource_content)

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        with mock_env({"MY_ENV": "foo"}):
            result = cache.get_value(raw_uri)

        assert endpoint.call_count == 1
        assert result.content == resource_content
        assert result.raw_uri == raw_uri
        assert result.resolved_uri == resolved_uri
        assert result.error is None
        assert result.is_cached is True
        assert result.is_dynamic is False
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0

    def test_dynamic_file_is_not_allowed_by_default(self):

        data_callback = Mock()
        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        raw_uri = "file:///root/${nested.value}/file.txt"

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result = cache.get_value(raw_uri, {"nested": {"value": "foo"}})

        assert result.content is None
        assert result.raw_uri == raw_uri
        assert result.resolved_uri is None
        assert result.error is not None
        assert result.error.context is ErrorContext.RESOLVE_URI
        assert isinstance(result.error.exception, RetrievalContextError)
        assert "dynamic file" in result.error.exception.message.lower()
        assert result.is_cached is False
        assert result.is_dynamic is True
        assert data_callback.call_count == 0
        assert update_callback.call_count == 0
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_resolved_from_event(self):

        resource_content = str(uuid4())

        def data_callback(getter: Getter):
            return str(getter.get_raw(), encoding="utf-8")

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        raw_uri = "https://example.dd/${nested.value}"
        resolved_uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, resolved_uri, body=resource_content)

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result = cache.get_value(raw_uri, {"nested": {"value": "foo"}})

        assert endpoint.call_count == 1
        assert result.content == resource_content
        assert result.raw_uri == raw_uri
        assert result.resolved_uri == resolved_uri
        assert result.error is None
        assert result.is_cached is True
        assert result.is_dynamic is True
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_error_on_resolve_uri_no_event(self):

        data_callback = Mock()
        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        unresolved_uri = "http://example.dd/${foo}"
        result = cache.get_value(unresolved_uri)

        assert result.content is None
        assert result.raw_uri == unresolved_uri
        assert result.resolved_uri is None
        assert result.error is not None
        assert result.error.context == ErrorContext.RESOLVE_URI
        assert isinstance(result.error.exception, RetrievalContextError)
        assert result.is_cached is False
        assert result.is_dynamic is True
        assert data_callback.call_count == 0
        assert update_callback.call_count == 0
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_error_on_resolve_uri_event_missing_key(self):

        data_callback = Mock()
        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        unresolved_uri = "http://example.dd/${foo}"
        result = cache.get_value(unresolved_uri, {"bar": "nope"})

        assert result.content is None
        assert result.raw_uri == unresolved_uri
        assert result.resolved_uri is None
        assert result.error is not None
        assert result.error.context == ErrorContext.RESOLVE_URI
        assert isinstance(result.error.exception, ValueError)
        assert result.is_cached is False
        assert result.is_dynamic is True
        assert data_callback.call_count == 0
        assert update_callback.call_count == 0
        assert cleanup_callback.call_count == 0

    @responses.activate
    @pytest.mark.parametrize(
        ["value"],
        [
            pytest.param(
                None,
                id="None",
            ),
            pytest.param(
                ["NO"],
                id="list",
            ),
            pytest.param(
                {"NO": "NO"},
                id="object",
            ),
        ],
    )
    def test_get_resource_error_on_resolve_uri_with_invalid_type(self, value):

        data_callback = Mock()
        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        unresolved_uri = "http://example.dd/${foo}"
        result = cache.get_value(unresolved_uri, {"foo": value})

        assert result.content is None
        assert result.raw_uri == unresolved_uri
        assert result.resolved_uri is None
        assert result.error is not None
        assert result.error.context == ErrorContext.RESOLVE_URI
        assert isinstance(result.error.exception, ValueError)
        assert result.is_cached is False
        assert result.is_dynamic is True
        assert data_callback.call_count == 0
        assert update_callback.call_count == 0
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_error_on_retrieve_uri(self):

        def data_callback(getter: Getter):
            return str(getter.get_raw(), encoding="utf-8")

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, uri, status=404)

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result = cache.get_value(uri)

        assert endpoint.call_count == 1

        assert result.content is None
        assert result.raw_uri == uri
        assert result.resolved_uri == uri
        assert result.error is not None
        assert result.error.context == ErrorContext.RETRIEVE_URI
        assert isinstance(result.error.exception, RefreshableGetterError)
        assert result.is_cached is True
        assert result.is_dynamic is False
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0

    @responses.activate
    def test_get_resource_error_on_handle_content(self):

        class MyErrorType(Exception): ...

        def data_callback(getter: Getter):
            value = str(getter.get_raw(), encoding="utf-8")
            raise MyErrorType(value)

        update_callback = Mock()
        cleanup_callback = Mock()
        tag = "my_cleanup_tag"
        uri = "https://example.dd/foo"
        endpoint = responses.add(responses.GET, uri, body="NOPE")

        cache = ResourceCache[str](
            tag=tag,
            on_data=data_callback,
            on_cleanup=cleanup_callback,
            on_update=update_callback,
        )

        result = cache.get_value(uri)

        assert endpoint.call_count == 1

        assert result.content is None
        assert result.raw_uri == uri
        assert result.resolved_uri == uri
        assert result.error is not None
        assert result.error.context == ErrorContext.HANDLE_CONTENT
        assert isinstance(result.error.exception, MyErrorType)
        assert result.is_cached is True
        assert result.is_dynamic is False
        assert update_callback.call_count == 1
        assert cleanup_callback.call_count == 0
