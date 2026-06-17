# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logprep.processor.deduplicator.rule import DeduplicatorRule


class TestDeduplicatorRule:
    def test_create_from_dict_returns_deduplicator_rule_with_fields(self):
        rule = {"filter": "field_1", "deduplicator": {"fields": ["field_1", "field_2"]}}
        deduplicator_rule = DeduplicatorRule.create_from_dict(rule)
        assert isinstance(deduplicator_rule, DeduplicatorRule)
        assert deduplicator_rule.fields == ["field_1", "field_2"]

    def test_create_from_dict_returns_deduplicator_rule_without_fields(self):
        rule = {"filter": "field_1", "deduplicator": {}}
        deduplicator_rule = DeduplicatorRule.create_from_dict(rule)
        assert isinstance(deduplicator_rule, DeduplicatorRule)
        assert deduplicator_rule.fields == []
