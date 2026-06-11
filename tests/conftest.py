"""Global configuration and fixtures for all pytest-based tests"""

from multiprocessing import set_start_method

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
