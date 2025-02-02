# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import tempfile

import ruamel.yaml

from logprep.processor.base.rule import Rule
from logprep.util.rule_loader import (
    DictRuleLoader,
    FileRuleLoader,
    ListRuleLoader,
    RuleLoader,
)

yaml = ruamel.yaml.YAML()


class TestDictRuleLoader:

    def setup_method(self):
        self.source = {"filter": "foo", "rule": {}}

    def test_object_hierarchy(self):
        assert isinstance(DictRuleLoader(self.source), RuleLoader)

    def test_returns_list(self):
        assert isinstance(DictRuleLoader(self.source).rules, list)

    def test_returns_list_of_rules(self):
        rules = DictRuleLoader(self.source).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)


class TestListRuleLoader:

    def setup_method(self):
        self.source = [{"filter": "foo", "rule": {}}, {"filter": "foo", "rule": {}}]

    def test_object_hierarchy(self):
        assert isinstance(ListRuleLoader(self.source), RuleLoader)

    def test_returns_list(self):
        assert isinstance(ListRuleLoader(self.source).rules, list)

    def test_returns_list_of_rules(self):
        rules = ListRuleLoader(self.source).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)
        assert len(rules) == 2


class TestFileRuleLoader:

    def setup_method(self):
        rules = [{"filter": "foo", "rule": {}}, {"filter": "foo", "rule": {}}]
        self.source = tempfile.mktemp()
        with open(self.source, "w", encoding="utf8") as file:
            yaml.dump(rules, file)

    def test_object_hierarchy(self):
        assert isinstance(FileRuleLoader(self.source), RuleLoader)

    def test_returns_list(self):
        assert isinstance(FileRuleLoader(self.source).rules, list)

    def test_returns_list_of_rules(self):
        rules = FileRuleLoader(self.source).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)
        assert len(rules) == 2
