"""Global configuration and fixtures for all pytest-based tests"""

import contextlib
import functools
import inspect
import json
from collections.abc import Generator, Sequence
from multiprocessing import active_children, set_start_method
from pathlib import Path
from typing import Callable
from unittest import mock

import pytest
import responses
from _pytest.mark.structures import ParameterSet
from prometheus_client import REGISTRY

from logprep.registry import Registry
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.environ import _ENV_SNAPSHOT
from logprep.util.getter import RefreshableGetter


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
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    yield


@pytest.fixture(autouse=True)
def clear_getter_cache():
    """Clear getter cache after each test"""
    RefreshableGetter.reset()


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


@pytest.fixture
def provision_context(tmp_path, monkeypatch) -> Generator[Callable[[dict], None]]:
    """
    Return a helper that provisions a ``test_cases`` context for a rule.

    The context is expected to have the following structure:
    .. code-block:: json

    {
        "http://example.tld/any/path": {
            "body": {
                "any": "json serializable content"
            },
            "content_type": "application/json", # default content_type
        }
        "https://...": { }, # same as http://
        "file://some/path/contents.txt": {
            "body": {
                "any": "json serializable content"
            }
        }
        "some/path/contents.txt": { } # same as file://
    }

    The helper covers the most relevant aspects of mocking and provisioning:
    - ``http://`` / ``https://`` are registered as mocked ``GET`` responses. The
      response is served as ``application/json`` unless the spec sets a
      ``content_type`` (e.g. ``text/plain``), in which case the body is still
      JSON-serialized but sent under that content type. Requests are automatically mocked
      using `responses`.
    - ``file://`` or a bare path is written into an isolated working directory the
      test is switched into, so a rule's relative file path resolves to it without
      any rewriting. The working directory is only changed when a file path is provided.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked_responses:

        def _provision(context: dict) -> None:
            for path, spec in context.items():
                if path.startswith(("http://", "https://")):
                    mocked_responses.add(
                        responses.GET,
                        path,
                        body=json.dumps(spec["body"]),
                        content_type=spec.get("content_type", "application/json"),
                    )
                else:
                    monkeypatch.chdir(tmp_path)
                    file_path = Path(path.removeprefix("file://"))
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(json.dumps(spec["body"]), encoding="utf-8")

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
