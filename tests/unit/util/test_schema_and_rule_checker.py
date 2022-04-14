# pylint: disable=missing-docstring
from logprep.util.schema_and_rule_checker import SchemaAndRuleChecker


class TestSchemaAndRuleChecker:
    def test_init(self):
        rule_checker = SchemaAndRuleChecker()
        assert isinstance(rule_checker.errors, list)
        assert len(rule_checker.errors) == 0
