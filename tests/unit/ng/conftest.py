import pytest

from logprep.registry import Registry


@pytest.fixture(autouse=True, scope="module")
def activate_ng():
    """Activate ng and ensure classes are preloaded"""
    Registry.set_ng_active(True)
    yield
    Registry.set_ng_active(False)
