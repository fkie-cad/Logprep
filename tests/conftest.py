"""Global configuration and fixtures for all pytest-based tests"""

from multiprocessing import set_start_method

import pytest


@pytest.fixture(autouse=True, scope="session")
def configure_multiprocess_start_method():
    """Sets the start method to 'fork' for all platforms and python versions"""
    set_start_method("fork", force=True)
