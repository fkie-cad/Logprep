"""This module is used to get documents that match a pre-detector filter."""

from typing import Optional
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class PreDetectorRuleError(InvalidRuleDefinitionError):
    """Base class for pre-detector rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"PreDetector rule ({message}): ")


class PreDetectorRule(Rule):
    """Check if documents match a filter."""

    def __init__(
        self,
        filter_rule: Optional[FilterExpression],
        detection_data: dict,
        ip_fields_to_check=None,
        description=None,
    ):
        super().__init__(filter_rule)
        self._ip_fields = ip_fields_to_check if ip_fields_to_check else list()
        self._description = description
        self._detection_data = detection_data

    def __eq__(self, other: "PreDetectorRule") -> bool:
        return (self._filter == other.filter) and (self._detection_data == other.detection_data)

    # pylint: disable=C0111
    @property
    def detection_data(self) -> dict:
        return self._detection_data

    @property
    def ip_fields(self) -> list:
        return self._ip_fields

    @property
    def description(self) -> str:
        return self._description

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "PreDetectorRule":
        PreDetectorRule._check_rule_validity(rule, "pre_detector")
        PreDetectorRule._check_if_pre_detection_data_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return PreDetectorRule(
            filter_expression,
            rule["pre_detector"],
            ip_fields_to_check=rule.get("ip_fields"),
            description=rule.get("description"),
        )

    @staticmethod
    def _check_if_pre_detection_data_valid(rule: dict):
        for item in ("id", "title", "severity", "case_condition"):
            if item not in rule["pre_detector"]:
                raise PreDetectorRuleError(f'Item "{item}" is missing in Predetector-Rule')

            if not isinstance(item, str):
                raise PreDetectorRuleError(f'Item "{item}" is not a string')

        if "mitre" not in rule["pre_detector"]:
            raise PreDetectorRuleError('Item "mitre" is missing in Predetector-Rule')

        if not isinstance(rule["pre_detector"]["mitre"], list):
            raise PreDetectorRuleError('Item "mitre" is not a list')

        for list_item in rule["pre_detector"]["mitre"]:
            if not isinstance(list_item, str):
                raise PreDetectorRuleError(f'List-Item "{list_item}"is not a string')
