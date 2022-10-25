"""This module is used to get documents that match a pre-detector filter."""

from attrs import define, field, validators, asdict

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class PreDetectorRuleError(InvalidRuleDefinitionError):
    """Base class for pre-detector rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"PreDetector rule ({message}): ")


class PreDetectorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Predetector"""

        id: str = field(validator=validators.instance_of(str), converter=str)
        title: str = field(validator=validators.instance_of(str))
        severity: str = field(validator=validators.instance_of(str))
        mitre: list = field(validator=validators.instance_of(list))
        case_condition: str = field(validator=validators.instance_of(str))

    def __eq__(self, other: "PreDetectorRule") -> bool:
        return all(
            [
                super().__eq__(other),
                self.ip_fields == other.ip_fields,
            ]
        )

    # pylint: disable=C0111
    @property
    def detection_data(self) -> dict:
        detection_data = asdict(self._config)
        for special_field in Rule.special_field_types:
            detection_data.pop(special_field)
        return detection_data

    @property
    def ip_fields(self) -> list:
        return self._config.ip_fields

    # Not used to check for equality, since it has not effect on the rule effects
    @property
    def description(self) -> str:
        return self._config.description

    # pylint: enable=C0111
