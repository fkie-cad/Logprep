# pylint: disable=protected-access
# pylint: disable=missing-docstring
from unittest import mock

from logprep.processor.dropper.processor import Dropper
from tests.unit.processor.base import BaseProcessorTestCase


class TestDropper(BaseProcessorTestCase):

    CONFIG = {
        "type": "dropper",
        "specific_rules": ["tests/testdata/unit/dropper/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/dropper/rules/generic/"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    def test_dropper_instantiates(self):
        rule = {"filter": "drop_me", "drop": ["drop_me"]}
        self._load_specific_rule(rule)
        assert isinstance(self.object, Dropper)

    def test_not_nested_field_gets_dropped_with_rule_loaded_from_file(self):
        expected = {}
        document = {"drop_me": "something"}
        self.object.process(document)

        assert document == expected

    def test_nested_field_gets_dropped(self):
        rule = {"filter": "drop.me", "drop": ["drop.me"]}
        expected = {}
        document = {"drop": {"me": "something"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_nested_field_with_neighbour_gets_dropped(self):
        rule = {"filter": "keep_me.drop_me", "drop": ["keep_me.drop_me"]}
        expected = {"keep_me": {"keep_me_too": "something"}}
        document = {"keep_me": {"drop_me": "something", "keep_me_too": "something"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_gets_dropped(self):
        rule = {"filter": "keep_me.drop.me", "drop": ["keep_me.drop.me"], "drop_full": False}
        expected = {"keep_me": {"drop": {}}}
        document = {"keep_me": {"drop": {"me": "something"}}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_gets_dropped_fully(self):
        rule = {"filter": "please.drop.me.fully", "drop": ["please.drop.me.fully"]}
        expected = {}
        document = {"please": {"drop": {"me": {"fully": "something"}}}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_with_neighbour_gets_dropped(self):
        rule = {"filter": "keep_me.drop.me", "drop": ["keep_me.drop.me"], "drop_full": False}
        expected = {"keep_me": {"drop": {}, "keep_me_too": "something"}}
        document = {"keep_me": {"drop": {"me": "something"}, "keep_me_too": "something"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_nested_field_with_child_gets_dropped(self):
        rule = {"filter": "drop.child", "drop": ["drop"]}
        expected = {}
        document = {"drop": {"child": "something"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_with_child_gets_dropped(self):
        rule = {"filter": "drop.me", "drop": ["drop.me"]}
        expected = {}
        document = {"drop": {"me": {"child": "foo"}}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_with_child_and_neighbour_gets_dropped(self):
        rule = {"filter": "drop.me", "drop": ["drop.me"]}
        expected = {"drop": {"neighbour": "bar"}}
        document = {"drop": {"me": {"child": "foo"}, "neighbour": "bar"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_with_child_and_not_drop_full_gets_partially_dropped(self):
        rule = {"filter": "drop.me", "drop": ["drop.me"], "drop_full": False}
        expected = {"drop": {}}
        document = {"drop": {"me": {"child": "foo"}}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_deep_nested_field_with_child_neighbour_and_not_drop_full_gets_partially_dropped(self):
        rule = {"filter": "drop.child", "drop": ["drop.child"], "drop_full": False}
        expected = {"drop": {"neighbour": "bar"}}
        document = {"drop": {"child": {"grand_child": "foo"}, "neighbour": "bar"}}
        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_apply_rules_is_called(self):
        rule = {"filter": "drop.child", "drop": ["drop.child"], "drop_full": False}
        document = {"drop": {"child": {"grand_child": "foo"}, "neighbour": "bar"}}
        self._load_specific_rule(rule)
        with mock.patch(
            f"{self.object.__module__}.{self.object.__class__.__name__}._apply_rules"
        ) as mock_apply_rules:
            self.object.process(document)
            mock_apply_rules.assert_called()

    def test_subkey_not_in_event(self):
        document = {
            "list": ["existing"],
            "key1": {
                "a": {"b": "value"},
            },
        }
        rule = {
            "filter": "key1",
            "dropper": {
                "drop": ["key1.a", "key1.b", "key1.key2.a", "key1.key2.key3.b"],
                "drop_full": False,
            },
        }
        self._load_specific_rule(rule)
        self.object.process(document)

    def test_key_not_in_event(self):
        document = {
            "list": ["existing"],
        }
        rule = {
            "filter": "list",
            "dropper": {
                "drop": ["key1.a"],
                "drop_full": False,
            },
        }
        self._load_specific_rule(rule)
        self.object.process(document)
