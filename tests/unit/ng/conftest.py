from unittest import mock

import pytest

from logprep.registry import Registry


@pytest.fixture(autouse=True)
def rewrite_registry_get_class_to_ng():
    get_class = Registry.get_class.__func__

    def get_class_wrapped(cls, component_type: str):
        if not component_type.startswith("ng_"):
            component_type = f"ng_{component_type}"
        return get_class(cls, component_type)

    with mock.patch.object(Registry, "get_class", classmethod(get_class_wrapped)):
        yield
