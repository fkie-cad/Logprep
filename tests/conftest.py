"""Global configuration and fixtures for all pytest-based tests"""

import functools
from multiprocessing import active_children, set_start_method
from unittest import mock

import pytest

from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import RefreshableGetter


@pytest.fixture(autouse=True)
def remove_interfering_env_variables(monkeypatch):
    """Remove environment variables which might interfere with tests"""
    monkeypatch.delenv("LOGPREP_GETTER_CONFIG", raising=False)
    monkeypatch.delenv(ENV_NAME_LOGPREP_GETTER_CONFIG, raising=False)
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.delenv("prometheus_multiproc_dir", raising=False)


@pytest.fixture(autouse=True)
def clear_getter_cache():
    """Clear getter cache after each test"""
    RefreshableGetter._shared.clear()  # pylint: disable=protected-access


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
