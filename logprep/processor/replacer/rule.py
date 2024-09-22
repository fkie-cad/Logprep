"""
Replacer
============

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given replacer rule

    filter: message
    replacer:
        ...
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    <INCOMMING_EVENT>

..  code-block:: json
    :linenos:
    :caption: Processed event

    <PROCESSED_EVENT>


.. autoclass:: logprep.processor.replacer.rule.ReplacerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for replacer:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.replacer.test_replacer
   :template: testcase-renderer.tmpl

"""

import re
from typing import Callable, List, Tuple

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule

REPLACE_ITEM = r"%{(.+)}"

REPLACEMENT_PATTERN = rf".*{REPLACE_ITEM}.*"
START = r"%\{"
END = r"\}"
REPLACEMENT = rf"(?P<replacement>[^{END}])"
DELIMITER = r"([^%]+)"
SEPARATOR = r"(\((?P<separator>\\\)|[^)]+)\))?"
SECTION_MATCH = rf"(?P<partition>(?!{START})){START}(?P<replacement>.*){END}(?P<delimiter>.*)"


class ReplacerRule(FieldManagerRule):
    """..."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for ReplacerRule"""

        source_fields: list = field(init=False, factory=list, eq=False)
        target_field: list = field(init=False, default="", eq=False)
        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.min_len(1),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(REPLACEMENT_PATTERN),
                ),
            ]
        )
        """A mapping of fieldnames to patterns to replace"""

    actions: dict

    def __init__(
        self, filter_rule: FilterExpression, config: "ReplacerRule.Config", processor_name: str
    ):
        super().__init__(filter_rule, config, processor_name)
        self._set_mapping_actions()

    def _set_mapping_actions(self):
        self.actions = {}
        for source_field, pattern in self._config.mapping.items():
            actions = []
            if not re.match(rf"^{REPLACEMENT_PATTERN}.*", pattern):
                pattern = "%{}" + pattern
            sections = re.findall(r"%\{[^%]+", pattern)
            for section in sections:
                section_match = re.match(SECTION_MATCH, section)
                replacement = section_match.group("replacement")
                delimiter = section_match.group("delimiter")
                delimiter = None if delimiter == "" else delimiter
                actions.append((section, replacement))
            self.actions[source_field] = actions
