"""
Grokker
============

The `grokker` processor ...

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given grokker rule

    filter: message
    grokker:
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


.. autoclass:: logprep.processor.grokker.rule.GrokkerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for grokker:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.grokker.test_grokker
   :template: testcase-renderer.tmpl

"""

import re

from attrs import define, field, validators

from logprep.processor.dissector.rule import DissectorRule
from logprep.util.grok.grok import GROK, Grok

DOTTED_FIELD_NOTATION = r"([^\[\]\{\}]*)*"
NOT_GROK = rf"(?!{GROK}).*"
MAPPING_VALIDATION_REGEX = re.compile(rf"^(({NOT_GROK})?{GROK}({NOT_GROK})?)*$")

FIELD_PATTERN = re.compile(r"%\{[A-Z0-9_]*?:([^\[\]]*?)(:.*)?\}")


def _dotted_field_to_logstash_converter(mapping: dict) -> dict:
    def _replace_pattern(pattern):
        fields = re.findall(FIELD_PATTERN, pattern)
        for dotted_field, _ in fields:
            splitted_field = dotted_field.split(".")
            if len(splitted_field) > 1:
                replacement = "".join(f"[{element}]" for element in splitted_field)
                pattern = re.sub(re.escape(dotted_field), replacement, pattern)
        return pattern

    return {dotted_field: _replace_pattern(pattern) for dotted_field, pattern in mapping.items()}


class GrokkerRule(DissectorRule):
    """..."""

    @define(kw_only=True)
    class Config(DissectorRule.Config):
        """Config for GrokkerRule"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(MAPPING_VALIDATION_REGEX),
                ),
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.min_len(1),
                ),
            ],
            converter=_dotted_field_to_logstash_converter,
        )
        """A mapping from source fields to a grok pattern.
        Dotted field notation is possible in key and in the grok pattern.
        Additionally logstash field notation is possible in grok pattern.
        """
        pattern_version: str = field(validator=validators.in_(("ecs", "legacy")), default="ecs")
        """(Optional) version for grok patterns
        - :code:`ecs`(default) -> use ecs complient output fields\n
        - :code:`legacy` -> use logstash legacy output fields
        """
        patterns: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """(Optional) additional grok patterns as mapping. E.g. :code:`CUSTOM_PATTERN: [^\s]*`
        if you want to use special target fields, you are able to use them an usual in the
        mapping sections. Here you only have to declare the matching regex without named groups.
        """

    def _set_mapping_actions(self):
        self.actions = {
            dotted_field: Grok(pattern, custom_patterns=self._config.patterns)
            for dotted_field, pattern in self._config.mapping.items()
        }

    def _set_convert_actions(self):
        pass
