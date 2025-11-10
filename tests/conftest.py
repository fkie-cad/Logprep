import pytest

from logprep.call_once import set_start_method_fork


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    set_start_method_fork()
