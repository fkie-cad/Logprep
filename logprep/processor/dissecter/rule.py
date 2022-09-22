from logprep.processor.base.rule import Rule


class DissecterRule(Rule):
    """dissecter rule"""

    def __eq__(self, other: "Rule") -> bool:
        return False

    @staticmethod
    def _create_from_dict(rule: dict) -> "DissecterRule":
        filter_expression = Rule._create_filter_expression(rule)
        return DissecterRule(filter_expression)
