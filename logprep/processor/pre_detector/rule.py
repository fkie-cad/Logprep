"""This module is used to get documents that match a pre-detector filter."""

from typing import Union
from attrs import define, field, validators, asdict

from logprep.processor.base.rule import Rule


class PreDetectorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Predetector"""

        id: str = field(validator=validators.instance_of((str, int)))
        title: str = field(validator=validators.instance_of(str))
        severity: str = field(validator=validators.instance_of(str))
        mitre: list = field(validator=validators.instance_of(list))
        case_condition: str = field(validator=validators.instance_of(str))
        ip_fields: list = field(validator=validators.instance_of(list), factory=list)
        """Used by the predetector to select ip_fields"""
        wildcard_fields: list = field(validator=validators.instance_of(list), factory=list)
        sigma_fields: Union[list, bool] = field(
            validator=validators.instance_of((list, bool)), factory=list
        )

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

    @property
    def description(self) -> str:
        return self._config.description

    # pylint: enable=C0111
