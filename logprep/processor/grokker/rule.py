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
from logprep.util.grok.grok import Grok

GROK = r"%\{([A-Z0-9_]*)(:[^\{\}\[\]:]*]*)?(:int|float)?\}"
NOT_GROK = rf"(?!{GROK}).*"
MAPPING_VALIDATION_REGEX = re.compile(rf"^(({NOT_GROK})?{GROK}({NOT_GROK})?)*$")


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
        )
        pattern_version: str = field(validator=validators.in_(("ecs", "legacy")), default="legacy")
        """A mapping from source fields to a grok pattern.
        Dotted field notation is possible in key and in the grok pattern.
        """

    def _set_mapping_actions(self):
        self.actions = {
            dotted_field: Grok(pattern) for dotted_field, pattern in self._config.mapping.items()
        }

    def _set_convert_actions(self):
        pass
