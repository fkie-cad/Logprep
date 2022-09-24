"""Dissecter Rule Module"""
from functools import partial
import re
from typing import Callable, List, Tuple
from attrs import define, validators, field, Factory
from logprep.processor.base.rule import Rule
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.helper import add_field_to

DISSECT = r"(%\{[A-Za-z0-9+&].*\})"
SEPERATOR = r"((?!%\{.*\}).+)"

append_as_list = partial(add_field_to, extends_lists=True)


def add_and_overwrite(event, target_field, content, _=None):
    """wrapper for add_field_to"""
    add_field_to(event, target_field, content, overwrite_output_field=True)


def append(event, target_field, content, seperator):
    """appends to event"""
    target_value = event.get(target_field)
    if isinstance(target_value, str):
        seperator = " " if seperator is None else seperator
        target_value = f"{seperator}".join([target_value, content])
        add_and_overwrite(event, target_field, target_value)
    else:
        append_as_list(event, target_field, content)


class DissecterRule(Rule):
    """dissecter rule"""

    @define(kw_only=True)
    class Config:
        """Config for Dissecter"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(rf"^({DISSECT}{SEPERATOR})+{DISSECT}$"),
                ),
            ],
            default=Factory(dict),
        )
        convert_datatype: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.in_(["float", "int", "string"]),
                ),
            ],
            default=Factory(dict),
        )
        tag_on_failure: list = field(
            validator=validators.instance_of(list), default=["_dissectfailure"]
        )

    _actions_mapping: dict = {
        "": add_and_overwrite,
        "+": append,
    }

    _config: "DissecterRule.Config"

    actions: List[Tuple[str, str, str, Callable]]
    """ List of tuples in format (<source_field>, <seperator>, <target_field>, <function>) """

    def __init__(self, filter_rule: FilterExpression, config: "DissecterRule.Config"):
        super().__init__(filter_rule)
        self._config = config
        self._set_actions()

    def __eq__(self, other: "DissecterRule") -> bool:
        return all((self._filter == other._filter, self._config == other._config))

    @staticmethod
    def _create_from_dict(rule: dict) -> "DissecterRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("dissecter")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = DissecterRule.Config(**config)
        return DissecterRule(filter_expression, config)

    def _set_actions(self):
        self.actions = []
        for source_field, pattern in self._config.mapping.items():
            sections = re.findall(r"%\{[^%]+", pattern)
            for section in sections:
                section_match = re.match(
                    r"%\{(?P<action>\+?)(?P<target_field>.*)\}(?P<seperator>.*)", section
                )
                seperator = (
                    section_match.group("seperator") if section_match.group("seperator") else None
                )
                action = (
                    section_match.group("action") if "action" in section_match.groupdict() else None
                )
                target_field = (
                    section_match.group("target_field")
                    if "target_field" in section_match.groupdict()
                    else None
                )
                if target_field:
                    action = self._actions_mapping.get(action)
                self.actions.append((source_field, seperator, target_field, action))
                assert True
