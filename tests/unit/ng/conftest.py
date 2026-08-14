import pytest

from logprep.framework.rule_tree import rule_tree
from logprep.ng.util import getter as ng_getter
from logprep.registry import Registry


# TODO: rule_tree packe need to be migrated to ng.
#  remove fixture after migration of rule_tree package to ng
@pytest.fixture(autouse=True)
def use_ng_getter_for_rule_tree(monkeypatch):
    monkeypatch.setattr(rule_tree, "getter", ng_getter)


@pytest.fixture(autouse=True, scope="module")
def activate_ng():
    """Activate ng and ensure classes are preloaded"""
    Registry.set_ng_active(True)
    yield
    Registry.set_ng_active(False)
