"""Global configuration and fixtures for all pytest-based tests"""

import contextlib
import functools
import inspect
import json
import re
import shutil
from collections import deque
from collections.abc import Generator, Sequence
from copy import deepcopy
from multiprocessing import active_children, set_start_method
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Literal, TypeAlias
from unittest import mock
from unittest.mock import MagicMock

import aiohttp
import pytest
import responses
from _pytest.mark.structures import ParameterSet
from aiointercept import CallbackResult, aiointercept
from attrs import define, field
from prometheus_client import REGISTRY

from logprep.ng.util.getter import HttpGetter as NGHttpGetter
from logprep.ng.util.getter import RefreshableGetter as NGRefreshableGetter
from logprep.registry import Registry
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.environ import _ENV_SNAPSHOT
from logprep.util.getter import HttpGetter, RefreshableGetter
from logprep.util.helper import MISSING, FieldValue, JsonObject, Missing


@pytest.fixture(autouse=True)
def remove_interfering_env_variables(monkeypatch):
    """Remove environment variables which might interfere with tests"""
    monkeypatch.delenv("LOGPREP_GETTER_CONFIG", raising=False)
    monkeypatch.delenv(ENV_NAME_LOGPREP_GETTER_CONFIG, raising=False)
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.delenv("prometheus_multiproc_dir", raising=False)


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test to prevent state pollution"""
    collectors = list(REGISTRY._collector_to_names.keys())  # pylint: disable=protected-access
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    yield


@pytest.fixture(autouse=True)
async def clear_getter_cache():
    """Clear legacy and NG getter caches and close shared HTTP sessions."""
    RefreshableGetter.reset()
    NGRefreshableGetter.reset()

    yield

    NGRefreshableGetter.reset()
    await NGHttpGetter.close_sessions()
    NGHttpGetter._credentials_registry.clear()  # pylint: disable=protected-access


def pytest_sessionstart(session):  # pylint: disable=unused-argument
    """Preload the cache on session start"""
    Registry.get_classes()  # imports non-ng modules
    Registry.set_ng_active(True)
    Registry.get_classes()  # imports non-ng modules
    Registry.set_ng_active(False)


@pytest.fixture(autouse=True, scope="session")
def configure_multiprocess_start_method():
    """Sets the start method to 'fork' for all platforms and python versions"""
    set_start_method("fork", force=True)


@pytest.fixture(autouse=True)
def run_atexit_functions_after_test():
    """Ensure cleanup functions registered through atexit are run after each test end"""
    callbacks = []
    with mock.patch(
        "atexit.register",
        lambda func, *args, **kwargs: callbacks.append(functools.partial(func, *args, **kwargs)),
    ):
        yield
    for callback in callbacks:
        callback()


@pytest.fixture(autouse=True, scope="session")
def cleanup_child_processes():
    """Kill any dangling child processes left by tests"""
    yield
    for child in active_children():
        child.terminate()
        child.join(timeout=2)


class _MockEnv(contextlib.ContextDecorator, contextlib.AsyncContextDecorator):
    """Context manager and decorator returned by :code:`mock_env`."""

    def __init__(self, env_dict):
        self._env_dict = env_dict
        self._original = None
        self._environ_patch = None

    def _recreate_cm(self):
        return type(self)(self._env_dict)

    def __enter__(self):
        self._original = dict(_ENV_SNAPSHOT)
        _ENV_SNAPSHOT.clear()
        _ENV_SNAPSHOT.update(self._env_dict)
        self._environ_patch = mock.patch("os.environ", self._env_dict)
        self._environ_patch.start()
        return _ENV_SNAPSHOT

    def __exit__(self, *exc_info):
        self._environ_patch.stop()
        _ENV_SNAPSHOT.clear()
        _ENV_SNAPSHOT.update(self._original)
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *exc_info):
        return self.__exit__(*exc_info)

    def __call__(self, func):
        if inspect.iscoroutinefunction(func):
            return contextlib.AsyncContextDecorator.__call__(self, func)
        return contextlib.ContextDecorator.__call__(self, func)


def mock_env(env_dict: dict) -> _MockEnv:
    """
    Mock helper to update the env snapshot.
    Supports sync / async and decorator / context manager use cases.

    Usage:
        @mock_env({"PYTEST_TEST_TOKEN": "mytoken"})
        def test_something():
            ...

        @mock_env({"PYTEST_TEST_TOKEN": "mytoken"})
        async def test_something_async():
            ...

        def test_something_else():
            with mock_env({"PYTEST_TEST_TOKEN": "mytoken"}):
                ...
    """
    return _MockEnv(env_dict)


class MockClientResponse(aiohttp.ClientResponse):
    """
    Workaround for aioresponses compatibility with aiohttp >= 3.14.

    aiohttp requires the 'stream_writer' argument, which aioresponses
    does not yet provide. Remove once upstream support is released.

    See: https://github.com/pnuckowski/aioresponses/pull/288
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("stream_writer", MagicMock(output_size=0))
        super().__init__(*args, **kwargs)


@define(kw_only=True, slots=True)
class File:
    """Mocks a file by providing either a json-body from code or a path to copy a file from"""

    path: str = ""
    source_path: str | None = None
    body: str | bytes | None = None
    json: FieldValue | Missing = MISSING

    def __post_init__(self):
        has_source = self.source_path is not None
        has_body = self.body is not None
        if has_source == has_body:
            if self.source_path is None and self.body is None:
                raise TypeError("Value needed for at least one: source_path, body")

            raise ValueError("Setting both source and body is not allowed.")


@define(kw_only=True)
class Response:
    status: int = 200
    reason: str | None = None
    body: str | bytes | None = None
    json: FieldValue | Missing = MISSING
    content_type: str | None = None
    headers: dict[str, str] | None = None

    def get_body(self) -> str | bytes | None:
        if self.json is not MISSING:
            return json.dumps(self.json)
        return self.body or ""

    def get_content_type(self) -> str:
        if self.content_type is not None:
            return self.content_type
        if self.json is not MISSING:
            return "application/json"
        return "text/plain"


@define(kw_only=True)
class Endpoint(Response):
    url: str | None = None
    url_pattern: str | re.Pattern[str] | None = None
    method: Literal["HEAD", "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"] = "GET"
    responses: Sequence[Response] | None = None
    repeat: bool | int = True
    _call_count: int = 0

    def get_url(self) -> str | re.Pattern[str]:
        if self.url_pattern is not None:
            if isinstance(self.url_pattern, str):
                return re.compile(self.url_pattern)
            return self.url_pattern
        if self.url is None:
            return re.compile(r"https?:.*")
        return self.url

    @property
    def call_count(self) -> int:
        return self._call_count

    def on_call(self, *_args, **_kwargs) -> None:
        self._call_count += 1

    def get_requests(self) -> Generator[tuple[Response, bool]]:
        if self.responses is None:
            yield self, True
        else:
            for index, res in enumerate(self.responses):

                yield res, index == (len(self.responses) - 1)


Context: TypeAlias = list[Endpoint | File]
BaseIP: str = "http://fdh"
BaseURL: str = "http://localhost"


@define(kw_only=True, slots=True, frozen=True)
class ProcessorTestCase:
    id: str
    rule: dict[str, Any]
    event: JsonObject
    expected: Any  # JsonObject failed for string_splitter
    expected_extras: list[tuple[JsonObject, list[tuple[str, str]]]] = field(factory=list)
    context: Context | None = None

    def case_to_param(self) -> ParameterSet:
        """Export a ProcessorTestCase as a Pytest-ParameterSet.
        Uses a deepcopy to avoid problems with in-place changes on event.
        """
        return pytest.param(deepcopy(self), id=self.id)


@define(kw_only=True, slots=True, frozen=True)
class ProcessorFailureTestCase(ProcessorTestCase):
    error_message: str


@pytest.fixture
async def provision_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> AsyncGenerator[Callable[[Any], None], None]:
    """Provision file and HTTP mocks for sync requests and async aiohttp clients."""
    project_root = pytestconfig.rootpath

    def _endpoint_callback(
        _url: Any,
        *,
        endpoint: Endpoint,
        responses: deque[Response],
        **_kwargs: Any,
    ) -> CallbackResult:
        endpoint.on_call()
        response = responses.popleft() if len(responses) > 1 else responses[0]

        return CallbackResult(
            status=response.status,
            reason=response.reason,
            body=response.get_body() or "",
            headers=response.headers,
            content_type=response.get_content_type(),
        )

    async with contextlib.AsyncExitStack() as stack:
        mocked_responses = stack.enter_context(
            responses.RequestsMock(assert_all_requests_are_fired=False)
        )
        mocked_aiohttp = await stack.enter_async_context(aiointercept(mock_external_urls=True))

        def _apply_provision_element(item: Any) -> bool:
            has_files = False
            if isinstance(item, list):
                for item in item:
                    return _apply_provision_element(item)

            elif isinstance(item, Endpoint):
                response_queue = deque(req for req, _ in item.get_requests())

                if response_queue:
                    repeat = item.repeat
                    if repeat is not True:
                        repeat = len(response_queue) - 1 + max(1, int(repeat))

                    mocked_aiohttp.add(
                        item.get_url(),
                        method=item.method,
                        repeat=repeat,
                        callback=functools.partial(
                            _endpoint_callback,
                            endpoint=item,
                            responses=response_queue,
                        ),
                    )

            elif isinstance(item, File):
                file_path = tmp_path / item.path.removeprefix("file://")
                file_path.parent.mkdir(parents=True, exist_ok=True)

                if item.source_path is not None:
                    ref_path = Path(item.source_path)
                    src_path = ref_path if ref_path.is_absolute() else project_root / ref_path
                    shutil.copy(src_path, file_path)
                elif item.json is not MISSING:
                    file_path.write_text(json.dumps(item.json), encoding="utf-8")
                elif isinstance(item.body, bytes):
                    file_path.write_bytes(item.body)
                else:
                    content = item.body or ""
                    assert isinstance(content, str)
                    file_path.write_text(content)

            elif isinstance(item, dict):
                for path, spec in item.items():
                    if path.startswith(("http://", "https://")):
                        body = spec.get("body")
                        assert body is not None

                        content_type = spec.get("content_type", "application/json")
                        method = spec.get("method", "GET")
                        status = spec.get("status", 200)
                        body = json.dumps(body)

                        mocked_responses.add(
                            responses.GET,
                            path,
                            body=body,
                            content_type=content_type,
                        )

                        mocked_aiohttp.add(
                            path,
                            method=method,
                            status=status,
                            body=body,
                            content_type=content_type,
                            repeat=True,
                        )

                    else:
                        has_files = True
                        file_path = tmp_path / path.removeprefix("file://")
                        file_path.parent.mkdir(parents=True, exist_ok=True)

                        if "source" in spec:
                            ref_path = Path(spec["source"])
                            src_path = (
                                ref_path if ref_path.is_absolute() else project_root / ref_path
                            )
                            shutil.copy(src_path, file_path)
                        else:
                            file_path.write_text(json.dumps(spec["body"]), encoding="utf-8")

            return has_files

        def _provision(*args: Any) -> None:
            has_files = False
            for item in args:
                has_files |= _apply_provision_element(item)
            if has_files:
                monkeypatch.chdir(tmp_path)

        yield _provision


def normalize_test_cases(*cases: ParameterSet) -> Sequence[ParameterSet]:
    """Pad ``test_cases`` entries that omit the trailing context."""
    padded = []
    for case in cases:
        values = tuple(case.values)
        if len(values) == 3:
            values = (*case.values, {})
        padded.append(pytest.param(*values, id=case.id, marks=case.marks))
    return padded


FIELD_VALUE_TEST_CASES = [
    pytest.param(0, id="int_0_falsy"),
    pytest.param(42, id="int_positive"),
    pytest.param(-1, id="int_negative_1"),
    pytest.param(-42, id="int_negative"),
    pytest.param(0.0, id="float_0.0_falsy"),
    pytest.param(42.1337, id="float_positive"),
    pytest.param(-42.1337, id="float_negative"),
    pytest.param(True, id="bool_true"),
    pytest.param(False, id="bool_false"),
    pytest.param([], id="list_empty_falsy"),
    pytest.param([1, 2, "string", 0.5, [1, 2, 3], {"key": "value"}], id="list_mixed_types"),
    pytest.param({}, id="dict_empty_falsy"),
    pytest.param({"key": "value"}, id="dict_simple"),
    pytest.param(
        {"key": {"str": "value", "int": 0, "float": 0.1, "bool": True, "list": [1, 2]}},
        id="dict_complex",
    ),
    pytest.param(None, id="None"),
]
