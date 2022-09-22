# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logprep.processor.dissecter.rule import DissecterRule


class DissecterRuleTest:
    def test_create_filter_expression_returns(self):
        rule = {"filter": "message", "dissecter": {"pattern": ""}}
        filter_expression = DissecterRule._create_filter_expression(rule)
        assert filter_expression
