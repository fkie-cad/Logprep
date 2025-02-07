# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import json
import tempfile

import pytest
import responses
import ruamel.yaml

from logprep.processor.base.rule import Rule
from logprep.processor.clusterer.rule import ClustererRule
from logprep.util.rule_loader import (
    DictRuleLoader,
    DirectoryRuleLoader,
    FileRuleLoader,
    RuleLoader,
)

yaml = ruamel.yaml.YAML()


class TestDictRuleLoader:

    def setup_method(self):
        self.source = {"filter": "foo", "calculator": {"calc": "1 + 1"}}
        self.name = "test instance name"
        self.args = (self.source, self.name)

    def test_returns_list(self):
        assert isinstance(DictRuleLoader(*self.args).rules, list)

    def test_returns_list_of_rules(self):
        rules = DictRuleLoader(*self.args).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)

    def test_raises_type_error_if_source_is_not_dict(self):
        self.source = "foo"
        with pytest.raises(TypeError, match="Expected a dictionary"):
            _ = DictRuleLoader(self.source, self.name).rules


class TestFileRuleLoader:

    def setup_method(self):
        rules = [
            {"filter": "foo", "calculator": {"calc": "1+1"}},
            {"filter": "foo", "calculator": {"calc": "2+2"}},
        ]
        self.source = tempfile.mktemp(suffix=".yml")
        with open(self.source, "w", encoding="utf8") as file:
            yaml.dump(rules, file)
        self.name = "test instance name"
        self.rule_class = Rule
        self.args = (self.source, self.name)

    def test_returns_list(self):
        assert isinstance(FileRuleLoader(*self.args).rules, list)

    def test_returns_list_of_rules(self):
        rules = FileRuleLoader(*self.args).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)
        assert len(rules) == 2

    def test_rules_raises_type_error_if_source_is_not_string(self):
        self.source = {"foo": "bar"}
        with pytest.raises(TypeError, match="Expected a string"):
            _ = FileRuleLoader(self.source, self.name).rules

    def test_rule_definitions_raises_type_error_if_source_is_not_string(self):
        self.source = {"foo": "bar"}
        with pytest.raises(TypeError, match="Expected a string"):
            _ = FileRuleLoader(self.source, self.name).rule_definitions


class TestDirectoryRuleLoader:

    def setup_method(self):
        rules = [
            {"filter": "foo", "calculator": {"calc": "6+5"}},
            {"filter": "foo", "calculator": {"calc": "1 + 1"}},
        ]
        self.source = tempfile.mkdtemp()
        yaml_files = [tempfile.mktemp(dir=self.source, suffix=".yml") for _ in range(2)]
        subdir = tempfile.mkdtemp(dir=self.source)
        json_files = [tempfile.mktemp(dir=subdir, suffix=".json") for _ in range(2)]
        for rule_file in yaml_files:
            with open(rule_file, "w", encoding="utf8") as file:
                yaml.dump(rules, file)
        for rule_file in json_files:
            with open(rule_file, "w", encoding="utf8") as file:
                file.write(json.dumps(rules))
        self.name = "test instance name"
        self.rule_class = Rule
        self.args = (self.source, self.name)

    def test_returns_list(self):
        assert isinstance(DirectoryRuleLoader(*self.args).rules, list)

    def test_returns_list_of_rules_for_json_and_yaml_files_recursively(self):
        rules = DirectoryRuleLoader(*self.args).rules
        assert rules, "Expected non-empty list of rules"
        assert all(isinstance(rule, Rule) for rule in rules)
        assert len(rules) == 8

    def test_rules_raises_type_error_if_source_is_not_string(self):
        self.source = {"foo": "bar"}
        with pytest.raises(TypeError, match="Expected a string"):
            _ = DirectoryRuleLoader(self.source, self.name).rules

    def test_rule_definitions_raises_type_error_if_source_is_not_string(self):
        self.source = {"foo": "bar"}
        with pytest.raises(TypeError, match="Expected a string"):
            _ = DirectoryRuleLoader(self.source, self.name).rule_definitions

    def test_returns_empty_list_if_no_valid_rule_files(self):
        self.source = tempfile.mkdtemp()
        invalid_file = tempfile.mktemp(dir=self.source, suffix=".txt")
        with open(invalid_file, "w", encoding="utf8") as file:
            file.write("invalid content")
        rules = DirectoryRuleLoader(self.source, self.name).rules
        assert rules == [], "Expected empty list of rules"

    def test_returns_empty_list_if_directory_is_empty(self):
        self.source = tempfile.mkdtemp()
        rules = DirectoryRuleLoader(self.source, self.name).rules
        assert rules == [], "Expected empty list of rules"


class TestRuleLoader:

    def test_get_rules_for_given_dict(self):
        rules_sources = {"filter": "foo", "calculator": {"calc": "1 + 1"}}
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_dicts(self):
        rules_sources = [
            {"filter": "foo", "calculator": {"calc": "1 + 1"}},
            {"filter": "foo", "calculator": {"calc": "2 + 2"}},
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_file_names(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/rule_with_custom_tests_1.yml",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_dirs(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/",
            "tests/testdata/auto_tests/clusterer/rules/",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_mixed_dirs_and_files(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_mixed_dirs_files_and_dicts(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/",
            {
                "filter": "message",
                "clusterer": {
                    "source_fields": ["message"],
                    "pattern": "test2 (signature) test2",
                    "repl": "<+>\\1</+>",
                },
            },
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_get_rules_for_given_list_of_mixed_dirs_files_and_dicts_for_different_processors(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            {
                "filter": "field1 AND field3",
                "calculator": {"calc": "${field1} + ${field3}", "target_field": "new_field"},
            },
            "tests/testdata/auto_tests/clusterer/rules/",
            {
                "filter": "message",
                "clusterer": {
                    "source_fields": ["message"],
                    "pattern": "test2 (signature) test2",
                    "repl": "<+>\\1</+>",
                },
            },
            "tests/testdata/unit/labeler/rules/rule.json",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)

    def test_rule_definitions_for_given_dict(self):
        rules_sources = {"filter": "foo", "calculator": {"calc": "1 + 1"}}
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_dicts(self):
        rules_sources = [
            {"filter": "foo", "calculator": {"calc": "1 + 1"}},
            {"filter": "foo", "calculator": {"calc": "2 + 2"}},
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_file_names(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/rule_with_custom_tests_1.yml",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_dirs(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/",
            "tests/testdata/auto_tests/clusterer/rules/",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_mixed_dirs_and_files(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_mixed_dirs_files_and_dicts(self):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/clusterer/rules/",
            {
                "filter": "message",
                "clusterer": {
                    "source_fields": ["message"],
                    "pattern": "test2 (signature) test2",
                    "repl": "<+>\\1</+>",
                },
            },
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_rule_definitions_for_given_list_of_mixed_dirs_files_and_dicts_for_different_processors(
        self,
    ):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            {
                "filter": "field1 AND field3",
                "calculator": {"calc": "${field1} + ${field3}", "target_field": "new_field"},
            },
            "tests/testdata/auto_tests/clusterer/rules/",
            {
                "filter": "message",
                "clusterer": {
                    "source_fields": ["message"],
                    "pattern": "test2 (signature) test2",
                    "repl": "<+>\\1</+>",
                },
            },
            "tests/testdata/unit/labeler/rules/rule.json",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    @responses.activate
    def test_rule_definitions_for_given_list_of_mixed_dirs_files_and_dicts_http_endpoints(
        self,
    ):
        responses.get(
            "http://example.com/rules.json",
            json={
                "filter": "field1 AND field3",
                "calculator": {"calc": "1+1", "target_field": "special_field"},
            },
        )
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            {
                "filter": "field1 AND field3",
                "calculator": {"calc": "${field1} + ${field3}", "target_field": "new_field"},
            },
            "tests/testdata/auto_tests/clusterer/rules/",
            {
                "filter": "message",
                "clusterer": {
                    "source_fields": ["message"],
                    "pattern": "test2 (signature) test2",
                    "repl": "<+>\\1</+>",
                },
            },
            "tests/testdata/unit/labeler/rules/rule.json",
            "http://example.com/rules.json",
        ]
        rules = RuleLoader(rules_sources, "test instance name").rule_definitions
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[-1], dict)
        assert "special_field" in rules[-1]["calculator"]["target_field"]

    def test_rule_from_file_ignores_files_with_invalid_rules(self, caplog):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/rules.json",
            "tests/testdata/auto_tests/labeler/schema.json",
        ]
        with caplog.at_level(10):
            rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)
        assert len(rules) == 2, "Expected 2 rules from clusterer"
        assert all(isinstance(rule, ClustererRule) for rule in rules)
        assert "WARNING" in caplog.text
        assert (
            "Loading rules from tests/testdata/auto_tests/labeler/schema.json"
            " failed: Unknown rule type -> Skipping"
        ) in caplog.text

    def test_rule_from_dir_ignores_files_with_invalid_rules(self, caplog):
        rules_sources = [
            "tests/testdata/unit/clusterer/rules/",
            "tests/testdata/auto_tests/labeler/",
        ]
        with caplog.at_level(10):
            rules = RuleLoader(rules_sources, "test instance name").rules
        assert rules
        assert isinstance(rules, list)
        assert isinstance(rules[0], Rule)
        assert len(rules) == 6, "Expected 6 rules"
        assert "WARNING" in caplog.text
        assert (
            "Loading rules from tests/testdata/auto_tests/labeler/schema.json"
            " failed: Unknown rule type -> Skipping"
        ) in caplog.text
