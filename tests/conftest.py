"""Global configuration and fixtures for all pytest-based tests"""

from multiprocessing import set_start_method
from unittest import mock

import pytest

from logprep.factory import Factory


@pytest.fixture(scope="session", autouse=True)
def configure_multiprocess_start_method():
    """Sets the start method to 'fork' for all platforms and python versions"""
    set_start_method("fork", force=True)


def create_with_auto_metric_setup(factory_create):
    def inner(*args, **kwargs):
        created_object = factory_create(*args, **kwargs)
        if hasattr(created_object, "setup_metrics"):
            created_object.setup_metrics()
        return created_object

    return inner


@pytest.fixture(autouse=True, scope="session")
def factory_with_automatic_metric_setup():
    with mock.patch.object(Factory, "create", wraps=create_with_auto_metric_setup(Factory.create)):
        yield
