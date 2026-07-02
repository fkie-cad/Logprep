"""Global configuration and fixtures for all pytest-based tests"""

import os
from multiprocessing import set_start_method

import pytest

os.environ.pop("LOGPREP_GETTER_CONFIG", None)
os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
os.environ.pop("prometheus_multiproc_dir", None)


@pytest.fixture(scope="session", autouse=True)
def configure_multiprocess_start_method():
    """Sets the start method to 'fork' for all platforms and python versions"""
    set_start_method("fork", force=True)
